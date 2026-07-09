from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional


class GateSeverity(str, Enum):
    BLOCK = "block"
    WARN = "warn"


@dataclass(frozen=True)
class RuntimeContext:
    job_id: str
    run_dir: Path
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrainTask:
    phase: str
    task_id: str = ""
    prompt: str = ""
    inputs: Mapping[str, Any] = field(default_factory=dict)
    expected_outputs: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkerTask:
    phase: str
    prompt: str
    task_id: str = ""
    inputs: Mapping[str, Any] = field(default_factory=dict)
    expected_outputs: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaskResult:
    status: str
    task_id: str = ""
    outputs: Mapping[str, Path] = field(default_factory=dict)
    details: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    changed_files: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    stdout_tail: str = ""


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    passed: bool
    severity: GateSeverity
    details: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    @property
    def p0(self) -> bool:
        return self.severity == GateSeverity.BLOCK and not self.passed

    @classmethod
    def pass_(cls, gate_id: str, details: str = "passed") -> "GateResult":
        return cls(
            gate_id=gate_id,
            passed=True,
            severity=GateSeverity.BLOCK,
            details=details,
        )

    @classmethod
    def fail(
        cls,
        gate_id: str,
        severity: GateSeverity = GateSeverity.BLOCK,
        details: str = "failed",
        evidence: Optional[Mapping[str, Any]] = None,
    ) -> "GateResult":
        return cls(
            gate_id=gate_id,
            passed=False,
            severity=severity,
            details=details,
            evidence=dict(evidence or {}),
        )


@dataclass(frozen=True)
class GateReport:
    results: List[GateResult]

    @property
    def blocked(self) -> bool:
        return any(result.p0 for result in self.results)

    @property
    def failed_blocks(self) -> List[str]:
        return [result.gate_id for result in self.results if result.p0]


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    sha256: str


@dataclass
class Dossier:
    job_id: str
    domain: str
    version: int = 3
    phases: Dict[str, str] = field(default_factory=dict)
    artifacts: Dict[str, ArtifactRef] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    gate_reports: List[Mapping[str, Any]] = field(default_factory=list)
    delegations: List[Mapping[str, Any]] = field(default_factory=list)

    def mark_phase(self, phase: str, status: str) -> None:
        if not phase:
            raise ValueError("phase is required")
        if not status:
            raise ValueError("status is required")
        self.phases[phase] = status

    def add_artifact(self, name: str, path: Path) -> None:
        from .dossier import hash_file

        if not name:
            raise ValueError("artifact name is required")
        self.artifacts[name] = ArtifactRef(path=str(path), sha256=hash_file(path))


PhaseHandler = Callable[[BrainTask, RuntimeContext], Mapping[str, Any]]


@dataclass(frozen=True)
class PhaseSpec:
    id: str
    handler: PhaseHandler
    prompt: str = ""
    expected_outputs: List[str] = field(default_factory=list)
    gate_ids: Optional[List[str]] = None
    repair_prompt: str = ""
    repair_expected_outputs: List[str] = field(default_factory=list)
    max_repair_attempts: int = 0
    review_rounds: int = 0
    # Freshness probe (ADR-001 §V4-C): when set, a resume must NOT skip this phase
    # while the probe reports the delivered artifact stale against its sources.
    # A callable keeps the engine core domain-neutral (no artifact-name strings
    # here); the domain pipeline supplies the predicate.
    staleness_probe: Optional[Callable[[Path], bool]] = None
