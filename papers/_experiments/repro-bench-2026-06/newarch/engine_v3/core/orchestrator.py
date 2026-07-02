from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Iterable

from engine_v3.artifacts import freeze_candidate_outputs

from .contracts import BrainTask, Dossier, PhaseSpec, RuntimeContext, TaskResult
from .dossier import DossierStore
from .gates import run_gates
from .runtime import Runtime


ENGINE_REVISION = "3.2"


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
        dossier.evidence.setdefault("engine_revision", ENGINE_REVISION)
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
                "engine_revision": dossier.evidence["engine_revision"],
                "skill_bundle": _skill_bundle(self.domain_pack),
                "runtime_policy": dossier.evidence["runtime_policy"],
            },
        )
        self.runtime.prepare(context)
        for phase in self.phases:
            if resume and dossier.phases.get(phase.id) == "done":
                _trace(dossier, "phase_skip_done", phase=phase.id)
                continue
            if _can_resume_preflight_recheck(dossier, phase, context.run_dir):
                _trace(
                    dossier,
                    "resume_preflight_gate_recheck",
                    phase=phase.id,
                    prior_status=dossier.phases.get(phase.id),
                )
                preflight_task = BrainTask(
                    task_id="%s:preflight" % phase.id,
                    phase=phase.id,
                    prompt=phase.prompt,
                    expected_outputs=list(phase.expected_outputs),
                )
                preflight_report = self._run_phase_handler_and_gates(phase, preflight_task, context, dossier)
                if not preflight_report.blocked:
                    dossier.mark_phase(phase.id, "done")
                    _trace(dossier, "resume_preflight_gate_passed", phase=phase.id)
                    self.dossier_store.save(dossier)
                    continue
                _trace(
                    dossier,
                    "resume_preflight_gate_blocked",
                    phase=phase.id,
                    failed_blocks=list(preflight_report.failed_blocks),
                )

            task = BrainTask(
                task_id="%s:brain" % phase.id,
                phase=phase.id,
                prompt=phase.prompt,
                expected_outputs=list(phase.expected_outputs),
            )
            runtime_result = _try_revalidation_source_artifact_fallback(
                phase=phase,
                task=task,
                context=context,
                dossier=dossier,
                runtime_result=TaskResult(
                    status="blocked",
                    task_id=task.task_id,
                    blockers=[
                        "missing declared output: %s" % rel
                        for rel in task.expected_outputs
                    ],
                ),
                runtime_name="%s+revalidation-bootstrap" % runtime_name,
                require_revalidation=True,
            )
            if runtime_result is not None:
                _trace(
                    dossier,
                    "revalidation_source_bootstrap_applied",
                    phase=phase.id,
                    task_id=runtime_result.task_id,
                    source_job_id=runtime_result.metadata.get("source_job_id"),
                    changed_files=list(runtime_result.changed_files),
                )
            if runtime_result is None:
                runtime_result = self._run_phase_task(task, context, dossier)
            repair_attempt = _prior_repair_attempts(dossier, phase.id)
            repair_budget_used = max(0, repair_attempt - _repair_budget_baseline(dossier, phase.id))
            if _starts_new_review_repair_budget(phase.id, runtime_result):
                repair_budget_used = 0
                _trace(
                    dossier,
                    "repair_budget_reset",
                    phase=phase.id,
                    latest_task_id=runtime_result.task_id,
                    next_attempt=repair_attempt + 1,
                    rationale="fresh Hermes review artifacts supersede prior stale/fallback repair attempts",
                )
            repairs_this_run = 0
            while (
                runtime_result is not None
                and runtime_result.status != "ok"
                and _runtime_result_repairable(runtime_result)
                and repair_budget_used < max(0, phase.max_repair_attempts)
            ):
                repair_attempt += 1
                repair_budget_used += 1
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
                fallback_result = _try_revalidation_source_artifact_fallback(
                    phase=phase,
                    task=task,
                    context=context,
                    dossier=dossier,
                    runtime_result=runtime_result,
                    runtime_name=runtime_name,
                )
                if fallback_result is not None:
                    runtime_result = fallback_result
                    _trace(
                        dossier,
                        "runtime_missing_outputs_fallback_applied",
                        phase=phase.id,
                        task_id=fallback_result.task_id,
                        source_job_id=fallback_result.metadata.get("source_job_id"),
                        fallback=fallback_result.metadata.get("fallback"),
                        changed_files=list(fallback_result.changed_files),
                    )
                else:
                    _trace(
                        dossier,
                        "runtime_missing_outputs_fallback_unavailable",
                        phase=phase.id,
                        blockers=list(runtime_result.blockers),
                    )
            if runtime_result is not None and runtime_result.status != "ok":
                if _can_handler_recheck_after_runtime_non_ok(phase, runtime_result):
                    _trace(
                        dossier,
                        "runtime_non_ok_handler_recheck_attempt",
                        phase=phase.id,
                        status=runtime_result.status,
                        blockers=list(runtime_result.blockers),
                    )
                    gate_report = self._run_phase_handler_and_gates(phase, task, context, dossier)
                    if not gate_report.blocked:
                        dossier.mark_phase(phase.id, "done")
                        _trace(dossier, "phase_done", phase=phase.id, route="handler_recheck_after_runtime_non_ok")
                        self.dossier_store.save(dossier)
                        continue
                    _trace(
                        dossier,
                        "runtime_non_ok_handler_recheck_failed",
                        phase=phase.id,
                        failed_blocks=list(gate_report.failed_blocks),
                    )
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
            while gate_report.blocked and repair_budget_used < max(0, phase.max_repair_attempts):
                repair_attempt += 1
                repair_budget_used += 1
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
                if (
                    gate_report.blocked
                    and repair_result is not None
                    and repair_result.status == "ok"
                    and not repair_result.changed_files
                ):
                    _trace(
                        dossier,
                        "repair_noop",
                        phase=phase.id,
                        attempt=repair_attempt,
                        failed_blocks=list(gate_report.failed_blocks),
                        rationale="repair returned ok without changed files and gates remained blocked",
                    )
                    repair_budget_used = max(repair_budget_used, max(0, phase.max_repair_attempts))
            if phase_failed:
                break
            else:
                if gate_report.blocked:
                    _maybe_record_human_checkpoint(dossier, phase.id, gate_report)
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

        if _maybe_require_vip_delivery_review(dossier, self.dossier_store.run_dir):
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
        _update_gate_substeps(dossier, phase.id, gate_report)
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
            skill_bundle_visible=list(context.metadata.get("skill_bundle") or []),
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


def _repair_budget_baseline(dossier: Dossier, phase_id: str) -> int:
    """Attempts made before a revalidation reset (e.g. invalid review
    provenance). They stay in the delegation audit trail but no longer count
    against the phase's repair budget."""
    baselines = dossier.evidence.get("repair_budget_baseline")
    if not isinstance(baselines, dict):
        return 0
    try:
        return max(0, int(baselines.get(phase_id) or 0))
    except (TypeError, ValueError):
        return 0


def _starts_new_review_repair_budget(phase_id: str, runtime_result: TaskResult | None) -> bool:
    if phase_id != "review_heal" or runtime_result is None or runtime_result.status != "ok":
        return False
    changed = set(runtime_result.changed_files or [])
    required = {"quality_review_round1.json", "quality_review_log.md"}
    return required.issubset(changed)


def _can_resume_preflight_recheck(dossier: Dossier, phase: PhaseSpec, run_dir: Path) -> bool:
    if not phase.gate_ids or dossier.phases.get(phase.id) not in {"blocked", "error"}:
        return False
    if not phase.expected_outputs:
        return True
    artifact_paths = {
        name
        for name, artifact in dossier.artifacts.items()
        if getattr(artifact, "sha256", "")
    }
    return all(rel in artifact_paths or (run_dir / rel).is_file() for rel in phase.expected_outputs)


def _repair_decision(phase: PhaseSpec, gate_report) -> dict:
    failed = set(gate_report.failed_blocks)
    if "A" in failed:
        route = "repair:data.verify_doi_two_sources:top_up_references"
        rationale = "reference or DOI evidence floor failed; top up and re-verify references"
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
    # stale = the task was supposed to overwrite a quarantined/fresh-required
    # output and did not; same repairability class as missing (run4: the
    # review_heal brain got a single attempt and terminally blocked because
    # stale blockers were not retryable).
    return bool(blockers) and all(
        str(blocker).startswith("missing declared output: ")
        or str(blocker).startswith("stale declared output: ")
        or str(blocker).startswith("watcher terminated hermes")
        for blocker in blockers
    )


def _can_handler_backfill_runtime_block(phase: PhaseSpec, result: TaskResult) -> bool:
    return phase.id == "data" and _runtime_result_repairable(result)


def _can_handler_recheck_after_runtime_non_ok(phase: PhaseSpec, result: TaskResult) -> bool:
    if phase.id in {"gap", "structure"} and _runtime_result_repairable(result):
        return True
    if phase.id == "write" and phase.max_repair_attempts > 0 and _runtime_result_repairable(result):
        return True
    if phase.id == "render_gates" and _runtime_result_repairable(result):
        return True
    return (
        bool(phase.gate_ids)
        and phase.id in {"data", "claim_evidence", "review_heal"}
        and result.status in {"blocked", "error"}
    )


def _try_revalidation_source_artifact_fallback(
    *,
    phase: PhaseSpec,
    task: BrainTask,
    context: RuntimeContext,
    dossier: Dossier,
    runtime_result: TaskResult,
    runtime_name: str,
    require_revalidation: bool = False,
) -> TaskResult | None:
    if phase.id != "data" or not _runtime_result_repairable(runtime_result):
        return None
    source_job_id = _revalidation_source_job_id(
        context.run_dir,
        require_revalidation=require_revalidation,
    )
    if source_job_id is None:
        return None
    jobs_dir = context.run_dir.parent.parent
    source_run_dir = jobs_dir / source_job_id / "run"
    if not source_run_dir.is_dir():
        return None

    changed_files: list[str] = []
    outputs: dict[str, Path] = {}
    for rel in task.expected_outputs:
        source = source_run_dir / rel
        if not source.is_file():
            return None
        target = context.run_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        changed_files.append(rel)
        outputs[rel] = target

    result = TaskResult(
        status="ok",
        task_id="%s:source_fallback" % phase.id,
        outputs=outputs,
        details="copied declared data outputs from source revalidation job",
        metadata={"source_job_id": source_job_id, "fallback": "revalidation_source_artifacts"},
        changed_files=changed_files,
        blockers=[],
    )
    candidate = freeze_candidate_outputs(
        context.run_dir,
        phase=phase.id,
        task_id=result.task_id,
        status=result.status,
        declared_outputs=list(task.expected_outputs),
        outputs=result.outputs,
        changed_files=result.changed_files,
        blockers=result.blockers,
    )
    _record_delegation(
        dossier=dossier,
        runtime_name="%s+source-fallback" % runtime_name,
        task=task,
        result=result,
        candidate=candidate,
    )
    for rel, path in result.outputs.items():
        dossier.add_artifact(rel, path)
    return result


def _revalidation_source_job_id(run_dir: Path, *, require_revalidation: bool = False) -> str | None:
    input_path = run_dir / "research_contract.input.json"
    if not input_path.is_file():
        return None
    try:
        contract = json.loads(input_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    metadata = contract.get("metadata")
    if not isinstance(metadata, dict):
        return None
    if require_revalidation and not metadata.get("revalidation"):
        return None
    source_job_id = metadata.get("source_job_id")
    if not isinstance(source_job_id, str):
        return None
    source_job_id = source_job_id.strip()
    if not re.fullmatch(r"v3_[A-Za-z0-9]+", source_job_id):
        return None
    return source_job_id


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
    substeps = phase_result.pop("substeps", None)
    if isinstance(substeps, list):
        dossier.evidence.setdefault("substeps", {})[phase_id] = [
            dict(step) for step in substeps if isinstance(step, dict)
        ]
    dossier.evidence.setdefault("phases", {})[phase_id] = phase_result


def _update_gate_substeps(dossier: Dossier, phase_id: str, gate_report) -> None:
    substeps_by_phase = dossier.evidence.get("substeps")
    if not isinstance(substeps_by_phase, dict):
        return
    substeps = substeps_by_phase.get(phase_id)
    if not isinstance(substeps, list):
        return
    failed_blocks = list(gate_report.failed_blocks)
    for step in substeps:
        if not isinstance(step, dict):
            continue
        if step.get("owner") != "validator":
            continue
        if not str(step.get("id") or "").startswith("gate_"):
            continue
        step["status"] = "blocked" if gate_report.blocked else "done"
        step["failed_blocks"] = failed_blocks


def _maybe_require_vip_delivery_review(dossier: Dossier, run_dir) -> bool:
    """D2 (V3_2_SPEC.md Decisions): a VIP job stops at human_review_required
    before final delivery even when every mechanical gate passes. Mechanical
    gates cannot verify grounding/judgment-level quality (the a64ad5b
    gate-widening incident shipped a fabricated paper past green gates).
    Approval is recorded in human_review_approval.json inside the run dir.
    """
    from pathlib import Path
    import json as _json

    phases = dict(getattr(dossier, "phases", {}) or {})
    if not phases or any(status != "done" for status in phases.values()):
        return False
    contract = {}
    for name in ("research_contract.json", "research_contract.input.json"):
        path = Path(run_dir) / name
        if path.is_file():
            try:
                loaded = _json.loads(path.read_text(encoding="utf-8"))
            except (OSError, _json.JSONDecodeError):
                continue
            if isinstance(loaded, dict):
                contract = loaded
                break
    tier = str(contract.get("level") or contract.get("tier") or "").strip().lower()
    if tier != "vip":
        return False
    approval_path = Path(run_dir) / "human_review_approval.json"
    approval = None
    if approval_path.is_file():
        try:
            approval = _json.loads(approval_path.read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            approval = None
    if isinstance(approval, dict) and approval.get("approved") is True:
        dossier.evidence["human_checkpoint"] = {
            "status": "approved",
            "phase": "delivery",
            "approved_by": approval.get("approved_by"),
            "approved_at": approval.get("approved_at"),
        }
        return True
    dossier.evidence["human_checkpoint"] = {
        "status": "human_review_required",
        "phase": "delivery",
        "reason": "VIP delivery requires a human quality review even when mechanical gates pass (V3_2_SPEC.md Decisions D2)",
        "options": ["approve_delivery", "request_revision", "stop_job"],
    }
    _trace(dossier, "human_review_required", phase="delivery")
    return True


def _maybe_record_human_checkpoint(dossier: Dossier, phase_id: str, gate_report) -> None:
    failed_blocks = list(gate_report.failed_blocks)
    if phase_id != "data" or not set(failed_blocks).intersection({"A", "E"}):
        return
    dossier.evidence["human_checkpoint"] = {
        "status": "human_decision_required",
        "phase": phase_id,
        "failed_blocks": failed_blocks,
        "reason": "data evidence could not satisfy hard gates within the configured repair budget",
        "options": [
            "revise_or_narrow_topic",
            "provide_more_seed_references",
            "downgrade_synthesis_type",
            "stop_job",
        ],
    }


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
