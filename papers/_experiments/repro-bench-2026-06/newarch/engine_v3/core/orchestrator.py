from __future__ import annotations

from typing import Iterable

from .contracts import BrainTask, Dossier, PhaseSpec, RuntimeContext
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

        context = RuntimeContext(job_id=job_id, run_dir=self.dossier_store.run_dir)
        self.runtime.prepare(context)
        for phase in self.phases:
            if resume and dossier.phases.get(phase.id) == "done":
                continue

            task = BrainTask(
                phase=phase.id,
                prompt=phase.prompt,
                expected_outputs=list(phase.expected_outputs),
            )
            phase_result = phase.handler(task, context)
            dossier.evidence[phase.id] = dict(phase_result or {})

            gate_report = run_gates(self.domain_pack, dossier, phase=phase.id)
            dossier.gate_reports.append(
                {
                    "phase": phase.id,
                    "blocked": gate_report.blocked,
                    "failed_blocks": gate_report.failed_blocks,
                }
            )
            if gate_report.blocked:
                dossier.mark_phase(phase.id, "blocked")
                self.dossier_store.save(dossier)
                break

            dossier.mark_phase(phase.id, "done")
            self.dossier_store.save(dossier)

        return dossier
