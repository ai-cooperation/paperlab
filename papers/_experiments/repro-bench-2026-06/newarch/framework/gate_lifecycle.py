"""Generic gate lifecycle (ENGINE_GENERAL_SPEC §2.2; DESIGN §3.8).

The FRAMEWORK owns the lifecycle: register -> run -> enforce -> block -> feed the
failure back as a dossier task. The concrete gates are the PACK's gate_registry();
this module never knows what "Gate A" or "body_too_thin" means.

Fail-closed: a gate whose check raises is recorded as a failed BLOCK (never a
silent pass) — a weak worker cannot make a gate disappear by crashing it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .domain_pack import DomainPack, GateResult, Severity


@dataclass(frozen=True)
class GateReport:
    results: list[GateResult]
    blocked: bool
    p0_count: int
    failed_blocks: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "p0_count": self.p0_count,
            "failed_blocks": self.failed_blocks,
            "results": [
                {"gate": r.gate, "severity": r.severity.value, "passed": r.passed,
                 "p0": r.p0, "details": r.details}
                for r in self.results
            ],
        }


def run_gates(pack: DomainPack, dossier: dict[str, Any], *, only: set[str] | None = None) -> GateReport:
    """Run the pack's registered gates against the dossier and enforce blocking.

    `only` optionally restricts to a subset of gate names (e.g. the gates due at a
    given checkpoint). The framework re-runs gates independently of the agent.
    """
    results: list[GateResult] = []
    for gate in pack.gate_registry():
        if only is not None and gate.name not in only:
            continue
        try:
            res = gate.check(dossier)
        except NotImplementedError as exc:
            res = GateResult(gate=gate.name, severity=gate.severity, passed=False,
                             p0=(gate.severity is Severity.BLOCK),
                             details=f"gate not implemented (fail-closed): {exc}")
        except Exception as exc:  # noqa: BLE001 - any gate error fails closed
            res = GateResult(gate=gate.name, severity=gate.severity, passed=False,
                             p0=(gate.severity is Severity.BLOCK),
                             details=f"gate raised (fail-closed): {type(exc).__name__}: {exc}")
        results.append(res)

    failed_blocks = [r.gate for r in results
                     if r.severity is Severity.BLOCK and not r.passed]
    p0_count = sum(1 for r in results if r.p0)
    return GateReport(results=results, blocked=bool(failed_blocks),
                      p0_count=p0_count, failed_blocks=failed_blocks)
