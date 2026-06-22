from __future__ import annotations

from typing import Iterable

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

        context = RuntimeContext(
            job_id=job_id,
            run_dir=self.dossier_store.run_dir,
            metadata={"skill_bundle": _skill_bundle(self.domain_pack)},
        )
        self.runtime.prepare(context)
        for phase in self.phases:
            if resume and dossier.phases.get(phase.id) == "done":
                continue

            task = BrainTask(
                task_id="%s:brain" % phase.id,
                phase=phase.id,
                prompt=phase.prompt,
                expected_outputs=list(phase.expected_outputs),
            )
            runtime_result = self._run_phase_task(task, context, dossier)
            if runtime_result is not None and runtime_result.status != "ok":
                dossier.mark_phase(phase.id, runtime_result.status)
                self.dossier_store.save(dossier)
                break

            phase_result = dict(phase.handler(task, context) or {})
            _apply_phase_result(dossier, phase.id, phase_result)

            only = set(phase.gate_ids) if phase.gate_ids is not None else None
            gate_report = run_gates(self.domain_pack, dossier, phase=phase.id, only=only)
            dossier.gate_reports.append(
                {
                    "phase": phase.id,
                    "blocked": gate_report.blocked,
                    "failed_blocks": gate_report.failed_blocks,
                    "results": [
                        {
                            "gate_id": result.gate_id,
                            "passed": result.passed,
                            "severity": result.severity.value,
                            "details": result.details,
                        }
                        for result in gate_report.results
                    ],
                }
            )
            if gate_report.blocked:
                dossier.mark_phase(phase.id, "blocked")
                self.dossier_store.save(dossier)
                break

            dossier.mark_phase(phase.id, "done")
            self.dossier_store.save(dossier)

        return dossier

    def _run_phase_task(
        self,
        task: BrainTask,
        context: RuntimeContext,
        dossier: Dossier,
    ) -> TaskResult | None:
        if not (task.prompt or task.expected_outputs):
            return None
        result = self.runtime.run_brain(task, context)
        _record_delegation(
            dossier=dossier,
            runtime_name=getattr(self.runtime, "name", "unknown"),
            task=task,
            result=result,
        )
        for rel, path in result.outputs.items():
            dossier.add_artifact(rel, path)
        return result


def _skill_bundle(domain_pack: object) -> list[str]:
    skill_bundle = getattr(domain_pack, "skill_bundle", None)
    if not callable(skill_bundle):
        return []
    return list(skill_bundle())


def _apply_phase_result(
    dossier: Dossier,
    phase_id: str,
    phase_result: dict,
) -> None:
    gate_inputs = phase_result.pop("gate_inputs", None)
    if isinstance(gate_inputs, dict):
        dossier.evidence.update(gate_inputs)
    dossier.evidence.setdefault("phases", {})[phase_id] = phase_result


def _record_delegation(
    dossier: Dossier,
    runtime_name: str,
    task: BrainTask,
    result: TaskResult,
) -> None:
    dossier.delegations.append(
        {
            "task_id": result.task_id or task.task_id,
            "phase": task.phase,
            "runtime": runtime_name,
            "class": "brain",
            "status": result.status,
            "declared_outputs": list(task.expected_outputs),
            "changed_files": list(result.changed_files),
            "blockers": list(result.blockers),
        }
    )
