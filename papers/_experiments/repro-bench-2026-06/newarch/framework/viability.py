"""Viability + tier interaction (DESIGN §5.1, §5.2).

One probe, branch by `level`. The pack owns "what makes this domain feasible"
(pack.viability_probe -> ViabilityVerdict); the framework owns the verdict shape,
the contract-hash lock, and the TIER BRANCH on a non-viable verdict:

  master       -> AUTONOMOUS pivot: apply the best candidate pivot + proceed, and
                  write a complete research_steering_log (discovery + why-pivoted +
                  what was discarded). Not silent — autonomous + fully transparent.
  phd/journal  -> STOP: write verdict + pivot options as pending_confirmation and
                  enter `paused_for_user` (no auto-run); resume only on confirmation.

The steering log is the generalized value_adjustment_log (§3.8 Gate E). Its quality
is first-class — the ONLY safeguard for the master auto-pivot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain_pack import DomainPack, ViabilityVerdict
from .domain_pack import contract_hash as _hash
from .dossier import Dossier

AUTONOMOUS_LEVELS = {"master"}
PAUSE_LEVELS = {"phd", "journal", "phd/journal"}


@dataclass
class ViabilityDecision:
    status: str                      # viable | auto_pivot | paused_for_user
    verdict: ViabilityVerdict
    applied_pivot: str | None = None
    steering_log: dict[str, Any] | None = None

    @property
    def can_proceed(self) -> bool:
        return self.status in ("viable", "auto_pivot")


def _steering_log(verdict: ViabilityVerdict, pivot: str) -> dict[str, Any]:
    """research_steering_log (§5.2): discovery + why-pivoted + what was discarded.
    First-class because it is the sole safeguard for the master auto-pivot."""
    return {
        "discovery": f"viability probe non-viable: {verdict.reason}",
        "metric": verdict.metric,
        "why_pivoted": f"applied the highest-ranked candidate pivot to recover viability: {pivot}",
        "discarded": [p for p in verdict.candidate_pivots if p != pivot],
        "contract_hash_before": verdict.contract_hash,
        "transparency": "autonomous master-level pivot, delivered alongside the report",
    }


def handle_viability(pack: DomainPack, contract: dict[str, Any], sources: dict[str, Any],
                     dossier: Dossier) -> ViabilityDecision:
    verdict = pack.viability_probe(contract, sources)
    dossier.set("viability", {
        "viable": verdict.viable, "reason": verdict.reason, "metric": verdict.metric,
        "candidate_pivots": verdict.candidate_pivots, "contract_hash": verdict.contract_hash,
        "tier_verdicts": verdict.tier_verdicts})

    if verdict.viable:
        dossier.update_status(phase="viable", blocked=False)
        return ViabilityDecision("viable", verdict)

    level = str(contract.get("level") or "master").lower()

    if level in AUTONOMOUS_LEVELS:
        pivot = verdict.candidate_pivots[0] if verdict.candidate_pivots else "reframe to the evidence"
        # ACTUALLY mutate the contract (codex 2026-06-16: a logged-only pivot lied that
        # status=auto_pivot meant a change). The deterministic, honest pivot for a thin
        # pooled estimate is a FRAMING downgrade — write the result as direction-and-
        # uncertainty, not a definitive estimate — applied to the contract + re-hashed.
        pivoted = {**(dossier.data.get("contract") or contract),
                   "value_framing": "direction_and_uncertainty",
                   "pivot_applied": pivot}
        new_hash = _hash(pivoted)
        log = _steering_log(verdict, pivot)
        log["contract_hash_after"] = new_hash
        log["applied_change"] = "value_framing -> direction_and_uncertainty"
        dossier.set("contract", pivoted)             # the contract IS changed now
        (dossier.run_dir / "research_steering_log.md").write_text(
            f"# Research steering log (autonomous master pivot)\n\n"
            f"- discovery: {log['discovery']}\n- why pivoted: {log['why_pivoted']}\n"
            f"- applied change: {log['applied_change']}\n- hash {verdict.contract_hash} -> {new_hash}\n"
            f"- discarded options: {log['discarded']}\n- transparency: {log['transparency']}\n",
            encoding="utf-8")
        dossier.pack_ext_set("research_steering_log", log)
        dossier.update_status(phase="pivoted", blocked=False, next_action=f"proceed with pivot: {pivot}")
        return ViabilityDecision("auto_pivot", verdict, applied_pivot=pivot, steering_log=log)

    # phd / journal -> STOP, await confirmation
    dossier.set("pending_confirmation", {
        "verdict": verdict.reason, "pivot_options": verdict.candidate_pivots,
        "metric": verdict.metric, "contract_hash": verdict.contract_hash})
    dossier.update_status(phase="paused_for_user", blocked=True,
                          blockers=["non-viable: awaiting user confirmation of a pivot"],
                          next_action="user confirms a pivot option, then resume")
    return ViabilityDecision("paused_for_user", verdict)
