"""Orchestrator control plane (DESIGN §3.3) — Python owns the LOOP, the brain owns
the THINKING. The deterministic wrapper owns the work-queue / state machine
(checkpoints, gates, which batch to dispatch next); the agent only decides the
content of the next batch and reasons inside it. This is the line that keeps the
engine from sliding back into the assembly line.

Phases are named steps. After each phase the wrapper checkpoints (dossier + atomic
manifest) and re-runs that phase's gates INDEPENDENTLY (a weak worker cannot skip a
gate). A FRESH session resumes from the dossier + checkpoint WITHOUT replaying
completed phases (the continuity primitive).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .dispatch import Dispatcher, WorkerPacket, WorkerResult
from .domain_pack import DomainPack
from .dossier import Dossier
from .gate_lifecycle import GateReport, run_gates


@dataclass
class Phase:
    name: str
    handler: Callable[["Orchestrator"], None]
    gates: frozenset[str] = field(default_factory=frozenset)   # gate names due after this phase
    checkpoint_artifacts: list[str] = field(default_factory=list)


class OrchestratorBlocked(Exception):
    """A BLOCK gate failed (or the watchdog tripped) — terminal, surfaced, never a
    silent pass."""

    def __init__(self, phase: str, report: GateReport | None = None, reason: str = ""):
        self.phase = phase
        self.report = report
        self.reason = reason or (f"gate block at {phase}: {report.failed_blocks}"
                                 if report else f"blocked at {phase}")
        super().__init__(self.reason)


class Orchestrator:
    def __init__(self, run_dir: Path, pack: DomainPack, dispatcher: Dispatcher,
                 phases: list[Phase], *, job_id: str | None = None,
                 contract: dict[str, Any] | None = None, max_steps: int = 64):
        self.run_dir = Path(run_dir)
        self.pack = pack
        self.dispatcher = dispatcher
        self.phases = phases
        self.max_steps = max_steps           # runaway watchdog (DESIGN §3.9)
        self._steps = 0
        if (self.run_dir / "dossier.json").is_file():
            self.dossier = Dossier.load(self.run_dir)        # fresh-resume seed
        else:
            self.dossier = Dossier.create(self.run_dir, job_id or "job",
                                          contract or {}, mode=pack.name)

    # ── resume (fresh session, no replay) ────────────────────────────────────
    @classmethod
    def resume(cls, run_dir: Path, pack: DomainPack, dispatcher: Dispatcher,
               phases: list[Phase], **kw: Any) -> "Orchestrator":
        """Construct from an existing dossier. run() will skip completed phases —
        it does NOT reload or replay their history."""
        return cls(run_dir, pack, dispatcher, phases, **kw)

    # ── state ────────────────────────────────────────────────────────────────
    def completed_phases(self) -> list[str]:
        return list(self.dossier.data.get("status", {}).get("completed", []))

    def _mark_complete(self, name: str) -> None:
        done = self.completed_phases()
        if name not in done:
            done.append(name)
        self.dossier.update_status(completed=done)

    # ── fan-out (parent-level only; records every delegation) ────────────────
    def fan_out(self, packets: list[WorkerPacket]) -> list[WorkerResult]:
        results: list[WorkerResult] = []
        for p in packets:
            self._steps += 1
            if self._steps > self.max_steps:
                raise OrchestratorBlocked(self.dossier.data["status"].get("phase", "?"),
                                          reason=f"watchdog: >{self.max_steps} dispatches")
            r = self.dispatcher.delegate(p)
            self.dossier.record_delegation(
                {"id": p.task_id, "task": p.task_goal, "worker_class": p.worker_class,
                 "model": p.resolved_model(), "status": r.status,
                 "outputs": r.changed_files})
            results.append(r)
        return results

    # ── the loop ─────────────────────────────────────────────────────────────
    def _run_phase(self, phase: Phase) -> None:
        self.dossier.update_status(phase=phase.name)
        phase.handler(self)                              # the brain reasons inside here
        if phase.gates:
            report = run_gates(self.pack, self.dossier.data, only=set(phase.gates))
            self.dossier.data.setdefault("gates", {})[phase.name] = report.as_dict()
            self.dossier.save()
            if report.blocked:
                self.dossier.update_status(blocked=True, blockers=report.failed_blocks)
                raise OrchestratorBlocked(phase.name, report)
        self._mark_complete(phase.name)
        self.dossier.checkpoint(phase.name,
                                next_action=f"begin phase after {phase.name}",
                                artifacts=phase.checkpoint_artifacts)

    def run(self) -> Dossier:
        for phase in self.phases:
            if phase.name in self.completed_phases():
                continue                                 # resume: do NOT replay
            self._run_phase(phase)
        self.dossier.update_status(phase="done", blocked=False)
        return self.dossier
