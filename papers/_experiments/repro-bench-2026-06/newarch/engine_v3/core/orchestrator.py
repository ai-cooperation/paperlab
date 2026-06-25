from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from engine_v3.artifacts import freeze_candidate_outputs

from .contracts import BrainTask, Dossier, PhaseSpec, RuntimeContext, TaskResult
from .dossier import DossierStore
from .gates import run_gates
from .runtime import Runtime


class EngineV3Orchestrator:
    def __init__(
        self,
        runtime: Runtime,
        domain_pack: object,
        phases: Iterable[PhaseSpec],
        dossier_store: DossierStore,
    ) -> None:
        self.runtime = runtime
        self.domain_pack = domain_pack
        self.phases = list(phases)
        self.dossier_store = dossier_store

    def run(self, job_id: str, resume: bool = True) -> Dossier:
        if resume and self.dossier_store.exists():
            dossier = self.dossier_store.load()
        else:
            domain = getattr(self.domain_pack, "name", "unknown")
            dossier = self.dossier_store.create(job_id=job_id, domain=domain)

        runtime_name = getattr(self.runtime, "name", "unknown")
        dossier.evidence.setdefault("runtime_policy", _runtime_policy(runtime_name))
        _trace(
            dossier,
            "runtime_selected",
            phase="system",
            runtime=runtime_name,
            fallback=dossier.evidence["runtime_policy"]["fallback"],
        )
        context = RuntimeContext(
            job_id=job_id,
            run_dir=self.dossier_store.run_dir,
            metadata={
                "skill_bundle": _skill_bundle(self.domain_pack),
                "runtime_policy": dossier.evidence["runtime_policy"],
            },
        )
        self.runtime.prepare(context)
        for phase in self.phases:
            if resume and dossier.phases.get(phase.id) == "done":
                _trace(dossier, "phase_skip_done", phase=phase.id)
                continue

            task = BrainTask(
                task_id="%s:brain" % phase.id,
                phase=phase.id,
                prompt=phase.prompt,
                expected_outputs=list(phase.expected_outputs),
            )
            runtime_result = self._run_phase_task(task, context, dossier)
            repair_attempt = _prior_repair_attempts(dossier, phase.id)
            repairs_this_run = 0
            while (
                runtime_result is not None
                and runtime_result.status != "ok"
                and _runtime_result_repairable(runtime_result)
                and repairs_this_run < max(0, phase.max_repair_attempts)
            ):
                repair_attempt += 1
                repairs_this_run += 1
                _trace(
                    dossier,
                    "repair_decision",
                    phase=phase.id,
                    attempt=repair_attempt,
                    route="repair_same_phase:missing_declared_outputs",
                    failed_blocks=[],
                    rationale="runtime did not produce declared outputs",
                )
                repair_task = BrainTask(
                    task_id="%s:repair:%s" % (phase.id, repair_attempt),
                    phase=phase.id,
                    prompt=_runtime_repair_prompt(phase, runtime_result, repair_attempt),
                    expected_outputs=list(phase.repair_expected_outputs or phase.expected_outputs),
                )
                runtime_result = self._run_phase_task(repair_task, context, dossier)
            if runtime_result is not None and runtime_result.status != "ok":
                dossier.mark_phase(phase.id, runtime_result.status)
                _trace(
                    dossier,
                    "phase_runtime_block",
                    phase=phase.id,
                    status=runtime_result.status,
                    blockers=list(runtime_result.blockers),
                )
                self.dossier_store.save(dossier)
                break

            gate_report = self._run_phase_handler_and_gates(phase, task, context, dossier)
            phase_failed = False
            while gate_report.blocked and repairs_this_run < max(0, phase.max_repair_attempts):
                repair_attempt += 1
                repairs_this_run += 1
                decision = _repair_decision(phase, gate_report)
                _trace(
                    dossier,
                    "repair_decision",
                    phase=phase.id,
                    attempt=repair_attempt,
                    route=decision["route"],
                    failed_blocks=list(gate_report.failed_blocks),
                    rationale=decision["rationale"],
                )
                repair_task = BrainTask(
                    task_id="%s:repair:%s" % (phase.id, repair_attempt),
                    phase=phase.id,
                    prompt=_repair_prompt(phase, gate_report, repair_attempt),
                    expected_outputs=list(phase.repair_expected_outputs or phase.expected_outputs),
                )
                repair_result = self._run_phase_task(repair_task, context, dossier)
                if repair_result is not None and repair_result.status != "ok":
                    gate_report = self._run_phase_handler_and_gates(phase, task, context, dossier)
                    if not gate_report.blocked:
                        _trace(
                            dossier,
                            "repair_nonzero_gate_passed",
                            phase=phase.id,
                            attempt=repair_attempt,
                            status=repair_result.status,
                        )
                        break
                    dossier.mark_phase(phase.id, repair_result.status)
                    _trace(
                        dossier,
                        "repair_failed",
                        phase=phase.id,
                        attempt=repair_attempt,
                        status=repair_result.status,
                        blockers=list(repair_result.blockers),
                    )
                    self.dossier_store.save(dossier)
                    phase_failed = True
                    break
                gate_report = self._run_phase_handler_and_gates(phase, task, context, dossier)
            if phase_failed:
                break
            else:
                if gate_report.blocked:
                    dossier.mark_phase(phase.id, "blocked")
                    _trace(
                        dossier,
                        "phase_blocked",
                        phase=phase.id,
                        failed_blocks=list(gate_report.failed_blocks),
                        repair_budget=phase.max_repair_attempts,
                    )
                    self.dossier_store.save(dossier)
                    break

            dossier.mark_phase(phase.id, "done")
            _trace(dossier, "phase_done", phase=phase.id)
            self.dossier_store.save(dossier)

        return dossier

    def _run_phase_handler_and_gates(
        self,
        phase: PhaseSpec,
        task: BrainTask,
        context: RuntimeContext,
        dossier: Dossier,
    ):
        phase_result = dict(phase.handler(task, context) or {})
        _apply_phase_result(dossier, phase.id, phase_result)

        only = set(phase.gate_ids) if phase.gate_ids is not None else None
        gate_report = run_gates(self.domain_pack, dossier, phase=phase.id, only=only)
        dossier.gate_reports.append(_gate_report_dict(phase.id, gate_report))
        _trace(
            dossier,
            "gate_report",
            phase=phase.id,
            blocked=gate_report.blocked,
            failed_blocks=list(gate_report.failed_blocks),
        )
        return gate_report

    def _run_phase_task(
        self,
        task: BrainTask,
        context: RuntimeContext,
        dossier: Dossier,
    ) -> TaskResult | None:
        if not (task.prompt or task.expected_outputs):
            return None
        result = self.runtime.run_brain(task, context)
        candidate = freeze_candidate_outputs(
            context.run_dir,
            phase=task.phase,
            task_id=result.task_id or task.task_id,
            status=result.status,
            declared_outputs=list(task.expected_outputs),
            outputs=result.outputs,
            changed_files=list(result.changed_files),
            blockers=list(result.blockers),
        )
        _record_delegation(
            dossier=dossier,
            runtime_name=getattr(self.runtime, "name", "unknown"),
            task=task,
            result=result,
            candidate=candidate,
        )
        _trace(
            dossier,
            "delegation",
            phase=task.phase,
            task_id=result.task_id or task.task_id,
            runtime=getattr(self.runtime, "name", "unknown"),
            status=result.status,
            changed_files=list(result.changed_files),
            blockers=list(result.blockers),
            candidate_manifest=candidate.get("manifest"),
            candidate_outputs=list(candidate.get("outputs") or []),
        )
        for rel, path in result.outputs.items():
            dossier.add_artifact(rel, path)
        return result


def _skill_bundle(domain_pack: object) -> list[str]:
    skill_bundle = getattr(domain_pack, "skill_bundle", None)
    if not callable(skill_bundle):
        return []
    return list(skill_bundle())


def _gate_report_dict(phase_id: str, gate_report) -> dict:
    return {
        "phase": phase_id,
        "blocked": gate_report.blocked,
        "failed_blocks": gate_report.failed_blocks,
        "results": [
            {
                "gate_id": result.gate_id,
                "passed": result.passed,
                "severity": result.severity.value,
                "details": result.details,
                "evidence": dict(result.evidence or {}),
            }
            for result in gate_report.results
        ],
    }


def _runtime_policy(runtime_name: str) -> dict:
    return {
        "production_target": "hermes-codex",
        "selected": runtime_name,
        "fallback": runtime_name != "hermes-codex",
    }


def _trace(dossier: Dossier, event: str, **payload) -> None:
    trace = dossier.evidence.setdefault("trace", [])
    if not isinstance(trace, list):
        trace = []
        dossier.evidence["trace"] = trace
    trace.append({"seq": len(trace) + 1, "event": event, **payload})


def _prior_repair_attempts(dossier: Dossier, phase_id: str) -> int:
    prefix = "%s:repair:" % phase_id
    attempts = []
    for delegation in dossier.delegations:
        task_id = str(delegation.get("task_id") or "")
        if not task_id.startswith(prefix):
            continue
        try:
            attempts.append(int(task_id.rsplit(":", 1)[-1]))
        except ValueError:
            continue
    return max(attempts, default=0)


def _repair_decision(phase: PhaseSpec, gate_report) -> dict:
    failed = set(gate_report.failed_blocks)
    if "A" in failed:
        route = "repair_same_phase:data_evidence"
        rationale = "reference or DOI evidence floor failed"
    elif "B" in failed:
        route = "repair_same_phase:claim_evidence"
        rationale = "claim-evidence consistency failed"
    elif failed.intersection({"C", "D", "F"}):
        route = "repair_same_phase:render_quality"
        rationale = "render, readability, or logic audit failed"
    elif "R" in failed:
        route = "review_self_heal"
        rationale = "review gate failed; reviewer/fixer loop required"
    elif "Z" in failed:
        route = "format_repair"
        rationale = "delivery artifact missing or invalid"
    else:
        route = "repair_same_phase"
        rationale = "blocking gate failed"
    return {
        "phase": phase.id,
        "route": route,
        "rationale": rationale,
    }


def _repair_prompt(phase: PhaseSpec, gate_report, attempt: int) -> str:
    gate_payload = _gate_report_dict(phase.id, gate_report)
    base = phase.repair_prompt or (
        "Repair this phase until all blocking gates pass. Preserve existing valid artifacts, "
        "replace insufficient artifacts, and do not stop at a diagnostic report."
    )
    return "\n\n".join([
        base,
        "Repair attempt: %s" % attempt,
        "Blocking gate report JSON:\n%s" % json.dumps(gate_payload, ensure_ascii=False, indent=2),
    ])


def _runtime_result_repairable(result: TaskResult) -> bool:
    if result.status != "blocked":
        return False
    blockers = list(result.blockers or [])
    return bool(blockers) and all(str(blocker).startswith("missing declared output: ") for blocker in blockers)


def _runtime_repair_prompt(phase: PhaseSpec, result: TaskResult, attempt: int) -> str:
    base = phase.repair_prompt or phase.prompt or "Repair missing declared outputs."
    return "\n".join(
        [
            base,
            "Repair attempt: %s" % attempt,
            "The previous runtime attempt ended before producing required declared outputs.",
            "Missing outputs:",
            *["- %s" % blocker for blocker in result.blockers],
            "Inspect the existing run directory, then write the declared outputs in place.",
        ]
    )


def _apply_phase_result(
    dossier: Dossier,
    phase_id: str,
    phase_result: dict,
) -> None:
    gate_inputs = phase_result.pop("gate_inputs", None)
    if isinstance(gate_inputs, dict):
        dossier.evidence.update(gate_inputs)
    artifacts = phase_result.pop("artifacts", None)
    if isinstance(artifacts, dict):
        for name, path in artifacts.items():
            dossier.add_artifact(str(name), Path(str(path)))
    dossier.evidence.setdefault("phases", {})[phase_id] = phase_result


def _record_delegation(
    dossier: Dossier,
    runtime_name: str,
    task: BrainTask,
    result: TaskResult,
    candidate: dict,
) -> None:
    delegation = {
        "task_id": result.task_id or task.task_id,
        "phase": task.phase,
        "runtime": runtime_name,
        "class": "brain",
        "status": result.status,
        "declared_outputs": list(task.expected_outputs),
        "changed_files": list(result.changed_files),
        "blockers": list(result.blockers),
    }
    if candidate:
        delegation["candidate_manifest"] = candidate.get("manifest")
        delegation["candidate_outputs"] = list(candidate.get("outputs") or [])
    dossier.delegations.append(delegation)
