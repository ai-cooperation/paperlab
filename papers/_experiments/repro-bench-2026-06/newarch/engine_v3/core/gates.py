from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Set

from .contracts import Dossier, GateReport, GateResult, GateSeverity


def run_gates(
    domain_pack: Any,
    dossier: Any,
    phase: Optional[str] = None,
    only: Optional[Set[str]] = None,
) -> GateReport:
    registry = getattr(domain_pack, "gate_registry", lambda: [])()
    results = []
    for spec in _selected_gates(registry, phase=phase, only=only):
        gate_id = _require_string(spec, "id")
        severity = _severity(spec.get("severity", GateSeverity.BLOCK))
        check = spec.get("check")
        if not callable(check):
            results.append(
                GateResult.fail(
                    gate_id,
                    severity=severity,
                    details="fail-closed: gate check is not callable",
                )
            )
            continue

        try:
            result = check(dossier)
        except Exception as exc:  # gate exceptions must become visible P0s.
            results.append(
                GateResult.fail(
                    gate_id,
                    severity=severity,
                    details="fail-closed: %s: %s" % (type(exc).__name__, exc),
                )
            )
            continue

        results.append(_normalise_result(gate_id, severity, result))
    return GateReport(results=results)


def _selected_gates(
    registry: Iterable[Mapping[str, Any]],
    phase: Optional[str],
    only: Optional[Set[str]],
) -> Iterable[Mapping[str, Any]]:
    for spec in registry:
        gate_id = str(spec.get("id", ""))
        if phase is not None and spec.get("phase") != phase:
            continue
        if only is not None and gate_id not in only:
            continue
        yield spec


def _require_string(spec: Mapping[str, Any], field: str) -> str:
    value = spec.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError("gate %s is required" % field)
    return value


def _severity(value: Any) -> GateSeverity:
    if isinstance(value, GateSeverity):
        return value
    return GateSeverity(str(value))


def _normalise_result(gate_id: str, severity: GateSeverity, result: Any) -> GateResult:
    if isinstance(result, GateResult):
        if result.severity == severity:
            return result
        return GateResult(
            gate_id=result.gate_id,
            passed=result.passed,
            severity=severity,
            details=result.details,
            evidence=result.evidence,
        )
    if isinstance(result, bool):
        if result:
            return GateResult(gate_id, True, severity, "passed")
        return GateResult.fail(gate_id, severity=severity)
    return GateResult.fail(
        gate_id,
        severity=severity,
        details="fail-closed: unsupported gate result type",
        evidence={"type": type(result).__name__},
    )

