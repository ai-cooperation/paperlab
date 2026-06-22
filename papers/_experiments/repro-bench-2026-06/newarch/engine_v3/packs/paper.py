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
    "claim_evidence",
    "write",
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

    def pipeline_plan(self) -> list[PhaseSpec]:
        return [
            PhaseSpec(id=phase_id, handler=_pending_phase_handler(phase_id))
            for phase_id in PAPER_PHASES
        ]

    def gate_registry(self) -> list[Mapping[str, Any]]:
        return [
            {
                "id": gate.name,
                "phase": _gate_phase(gate.name),
                "severity": _v3_severity(gate.severity),
                "check": _adapt_gate_check(gate.check),
            }
            for gate in self._v2.gate_registry()
        ]

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
    }.get(gate_name, "")


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
