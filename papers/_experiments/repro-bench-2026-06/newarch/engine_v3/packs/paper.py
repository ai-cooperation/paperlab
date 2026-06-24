from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

import paperctl
from framework import canonicalize_contract as v2_canonicalize_contract
from framework import contract_hash as v2_contract_hash
from framework import Severity as V2Severity
from packs.paper import PaperPack as V2PaperPack

from engine_v3.core import GateResult, GateSeverity, PhaseSpec, RuntimeContext, BrainTask


PAPER_SKILL_BUNDLE = [
    "paper-draft",
    "literature-synthesis",
    "innovation-positioning",
    "figure-design",
    "qmd-writer",
    "paper-review-skill",
    "academic-writing",
    "journal-templates",
    "elite-reviewer-audit",
    "paper-logic-audit",
    "figure-table-checker",
    "dataset-fetch",
    "survey-weighted-analysis",
    "number-trace-writing",
]


PAPER_PHASES = [
    "data",
    "gap",
    "structure",
    "write",
    "claim_evidence",
    "render_gates",
    "review_heal",
    "format_repair",
]


class PaperToolProvider:
    name = "paper-tools"

    def capabilities(self) -> Mapping[str, Any]:
        return {
            "tools": sorted(_TOOL_HANDLER_NAMES),
            "runner": "direct-python",
        }

    def run(self, tool_name: str, args: Mapping[str, Any]) -> Mapping[str, Any]:
        handler_name = _TOOL_HANDLER_NAMES.get(tool_name)
        if handler_name is None:
            raise KeyError("unknown paper tool: %s" % tool_name)

        handler = getattr(paperctl, handler_name)
        run_dir = _run_dir(args)
        if tool_name == "gate":
            gate = str(args.get("gate") or "")
            if not gate:
                raise ValueError("gate is required for paper tool: gate")
            exit_code = handler(run_dir, gate)
        else:
            exit_code = handler(run_dir)
        return {
            "status": "ok" if exit_code == 0 else "failed",
            "exit_code": exit_code,
            "tool": tool_name,
        }


class PaperPack:
    name = "paper"

    def __init__(self) -> None:
        self._v2 = V2PaperPack()

    def contract_schema(self) -> Mapping[str, Any]:
        return {
            "type": "object",
            "required": ["topic", "research_question", "synthesis"],
            "properties": {
                "topic": {"type": "string"},
                "research_question": {"type": "string"},
                "target_journal": {"type": "string"},
                "synthesis": {"type": "object"},
                "data_source": {"type": "object"},
            },
        }

    def parse_contract(self, raw: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._v2.parse_contract(dict(raw))

    def canonicalize_contract(self, contract: Mapping[str, Any]) -> Mapping[str, Any]:
        return v2_canonicalize_contract(dict(contract))

    def contract_hash(self, contract: Mapping[str, Any]) -> str:
        return v2_contract_hash(dict(contract))

    def skill_bundle(self) -> list[str]:
        return list(PAPER_SKILL_BUNDLE)

    def tool_provider(self) -> PaperToolProvider:
        return PaperToolProvider()

    def viability_probe(self, contract: Mapping[str, Any], sources: Mapping[str, Any]) -> Any:
        return self._v2.viability_probe(dict(contract), dict(sources))

    def pipeline_plan(self) -> list[PhaseSpec]:
        return [
            PhaseSpec(id=phase_id, handler=_pending_phase_handler(phase_id))
            for phase_id in PAPER_PHASES
        ]

    def gate_registry(self) -> list[Mapping[str, Any]]:
        gates = [
            {
                "id": gate.name,
                "phase": _gate_phase(gate.name),
                "severity": _v3_severity(gate.severity),
                "check": _adapt_gate_check(gate.check),
            }
            for gate in self._v2.gate_registry()
        ]
        gates.extend([
            {
                "id": "R",
                "phase": "review_heal",
                "severity": GateSeverity.BLOCK,
                "check": _gate_review,
            },
            {
                "id": "Z",
                "phase": "format_repair",
                "severity": GateSeverity.BLOCK,
                "check": _gate_delivery,
            },
        ])
        return gates

    def status_projection(
        self,
        dossier: Mapping[str, Any],
        run_dir: Path,
    ) -> Mapping[str, Any]:
        return {
            "domain": self.name,
            "run_dir": str(run_dir),
            "phases": dict(dossier.get("phases", {})),
            "artifacts": dict(dossier.get("artifacts", {})),
        }


def _pending_phase_handler(phase_id: str) -> Callable[[BrainTask, RuntimeContext], Mapping[str, Any]]:
    def _handler(_task: BrainTask, _context: RuntimeContext) -> Mapping[str, Any]:
        return {"phase": phase_id, "status": "pending"}

    return _handler


def _adapt_gate_check(check: Callable[[dict], Any]) -> Callable[[Any], GateResult]:
    def _check(dossier: Any) -> GateResult:
        raw = check(_dossier_to_dict(dossier))
        severity = _v3_severity(raw.severity)
        return GateResult(
            gate_id=raw.gate,
            passed=bool(raw.passed),
            severity=severity,
            details=str(raw.details or ""),
            evidence=dict(raw.evidence or {}),
        )

    return _check


def _dossier_to_dict(dossier: Any) -> dict[str, Any]:
    if isinstance(dossier, dict):
        return dossier
    base = dict(getattr(dossier, "evidence", {}))
    base.update({
        "job_id": getattr(dossier, "job_id", ""),
        "domain": getattr(dossier, "domain", ""),
        "phases": dict(getattr(dossier, "phases", {})),
        "artifacts": dict(getattr(dossier, "artifacts", {})),
    })
    return base


def _v3_severity(severity: Any) -> GateSeverity:
    if severity == V2Severity.WARN or str(severity).upper().endswith("WARN"):
        return GateSeverity.WARN
    return GateSeverity.BLOCK


def _gate_phase(gate_name: str) -> str:
    return {
        "A": "data",
        "B": "claim_evidence",
        "C": "render_gates",
        "D": "render_gates",
        "E": "data",
        "F": "render_gates",
        "R": "review_heal",
        "Z": "format_repair",
    }.get(gate_name, "")


def _gate_review(dossier: Any) -> GateResult:
    data = _dossier_to_dict(dossier)
    review = data.get("review") if isinstance(data.get("review"), dict) else {}
    p0_count = _review_p0_count(review)
    delivery = str(review.get("delivery") or _review_delivery(review) or "").lower()
    floor = review.get("floor_100")
    if floor is None:
        floor = review.get("quality_gate", {}).get("floor_100") if isinstance(review.get("quality_gate"), dict) else None
    loop = review.get("review_loop") if isinstance(review.get("review_loop"), dict) else {}
    loop_ok = _review_loop_ok(loop, bool(data.get("review_log_present")))
    ok = (
        p0_count == 0
        and delivery in ("pass", "passed", "ok")
        and isinstance(floor, (int, float))
        and loop_ok
    )
    return GateResult(
        gate_id="R",
        passed=ok,
        severity=GateSeverity.BLOCK,
        details=(
            "review passed: no P0, delivery pass, floor_100=%s, loop ok" % floor
            if ok else
            "review failed: p0_count=%s, delivery=%s, floor_100=%s, loop_ok=%s" % (
                p0_count,
                delivery or None,
                floor,
                loop_ok,
            )
        ),
        evidence={
            "p0_count": p0_count,
            "delivery": delivery,
            "floor_100": floor,
            "review_loop": loop,
            "review_log_present": bool(data.get("review_log_present")),
        },
    )


def _review_p0_count(review: Mapping[str, Any]) -> int:
    if "p0_count" in review:
        return int(review.get("p0_count") or 0)
    findings = review.get("findings")
    if not isinstance(findings, list):
        return 0
    return sum(
        1
        for finding in findings
        if isinstance(finding, dict)
        and str(finding.get("status") or "").lower() == "open"
        and str(finding.get("severity") or "").lower() in {"critical", "p0"}
    )


def _review_delivery(review: Mapping[str, Any]) -> str:
    quality_gate = review.get("quality_gate")
    if isinstance(quality_gate, dict):
        status = str(quality_gate.get("status") or "").lower()
        if status in {"pass", "passed", "ok"}:
            return "pass"
    summary = review.get("summary")
    if isinstance(summary, dict) and summary.get("blocking_for_final_submission"):
        return "revise"
    return str(review.get("overall_status") or "")


def _review_loop_ok(loop: Mapping[str, Any], log_present: bool) -> bool:
    if not log_present:
        return False
    status = str(loop.get("status") or "").lower()
    rounds = loop.get("rounds")
    reviewer = str(loop.get("reviewer_model") or "")
    fixer = str(loop.get("fixer_model") or "")
    independent = bool(loop.get("independent_reviewer"))
    floor_failed = bool(loop.get("floor_failed"))
    return (
        status in {"passed", "pass", "done"}
        and isinstance(rounds, int)
        and rounds >= 1
        and bool(reviewer)
        and bool(fixer)
        and independent
        and not floor_failed
    )


def _gate_delivery(dossier: Any) -> GateResult:
    artifacts = getattr(dossier, "artifacts", {}) if not isinstance(dossier, dict) else dossier.get("artifacts", {})
    pdf = artifacts.get("paper_draft_v0.pdf") if isinstance(artifacts, dict) else None
    ok = pdf is not None and bool(getattr(pdf, "sha256", "") or (isinstance(pdf, dict) and pdf.get("sha256")))
    return GateResult(
        gate_id="Z",
        passed=ok,
        severity=GateSeverity.BLOCK,
        details="delivery PDF present" if ok else "delivery PDF missing from artifact index",
        evidence={"artifact": "paper_draft_v0.pdf", "present": ok},
    )


def _run_dir(args: Mapping[str, Any]) -> Path:
    raw = args.get("run_dir")
    if raw is None:
        raise ValueError("run_dir is required")
    return Path(str(raw)).expanduser()


_TOOL_HANDLER_NAMES = {
    "refs.build_from_dois": "cmd_refs_build_from_dois",
    "refs.audit": "cmd_refs_audit",
    "data.meta_analysis": "cmd_data_meta_analysis",
    "figures.meta": "cmd_figures_meta",
    "tables.inject": "cmd_tables_inject",
    "render": "cmd_render",
    "review.compile": "cmd_review_compile",
    "provenance": "cmd_provenance",
    "gate": "cmd_gate_pack",
}
