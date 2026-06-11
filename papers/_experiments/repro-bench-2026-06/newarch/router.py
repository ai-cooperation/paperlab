#!/usr/bin/env python3
"""Routing policy for the paper job service.

This module is intentionally policy-only. It does not run data probes,
experiments, model calls, or rendering. The job runner consumes the returned
decision and remains the executor.
"""
from __future__ import annotations

from typing import Any


REQUIRED_CONTRACT_KEYS = (
    "job_id",
    "source",
    "level",
    "tier",
    "topic",
    "research_question",
    "contribution",
    "data_source",
    "target_journal",
)

LEVELS = {"master", "phd", "journal"}
TIERS = {"free", "vip"}
LEGACY_MODEL_POLICIES = {"free_only", "free", "vip", "paid", "by_tier"}
JOURNAL_Q_THRESHOLDS = {
    "q1": 8.0,
    "q2": 7.5,
    "q3": 7.0,
    "q4": 6.5,
}

# Tier policy (user-defined): guests have no MCP access (enforced b-side).
# member (tier=free)  -> master level only, CPU only, content threshold 7.5
# vip                 -> up to phd, threshold 8.0; GPU possible but ONLY after
#                        manual approval (job blocks + notifies; never auto-runs)
TIER_MAX_LEVEL = {"free": {"master"}, "vip": {"master", "phd", "journal"}}
LEVEL_THRESHOLDS = {"master": 7.5, "phd": 8.0}
OUTPUT_LANGUAGES = {"zh", "en"}


def requested_compute(contract: dict[str, Any]) -> str:
    method = contract.get("method")
    compute = (method or {}).get("compute") if isinstance(method, dict) else None
    return str(compute or "cpu").lower()


def validate_contract(contract: dict[str, Any]) -> None:
    missing = [key for key in REQUIRED_CONTRACT_KEYS if key not in contract]
    if missing:
        raise ValueError(f"research_contract missing required keys: {missing}")
    if not isinstance(contract.get("data_source"), dict):
        raise ValueError("research_contract.data_source must be an object")
    data_source = contract["data_source"]
    for key in ("name", "type", "probe_required"):
        if key not in data_source:
            raise ValueError(f"research_contract.data_source missing required key: {key}")
    if not str(contract.get("job_id") or "").strip():
        raise ValueError("research_contract.job_id must be non-empty")
    if contract.get("source") != "paper-mcp":
        raise ValueError(f"unsupported source: {contract.get('source')}")
    if contract.get("level") not in LEVELS:
        raise ValueError(f"unsupported level: {contract.get('level')}")
    if contract.get("tier") not in TIERS:
        raise ValueError(f"unsupported tier: {contract.get('tier')}")
    if "model_policy" in contract:
        if contract.get("model_policy") not in LEGACY_MODEL_POLICIES:
            raise ValueError(f"unsupported model_policy: {contract.get('model_policy')}")
        if contract.get("tier") == "free" and contract.get("model_policy") in {"vip", "paid"}:
            raise ValueError("free tier cannot request vip model_policy")
    tier = str(contract.get("tier"))
    level = str(contract.get("level"))
    if level not in TIER_MAX_LEVEL.get(tier, set()):
        raise ValueError(
            f"level '{level}' requires a higher membership tier "
            f"(tier '{tier}' allows: {sorted(TIER_MAX_LEVEL.get(tier, set()))})")
    if requested_compute(contract) == "gpu" and tier != "vip":
        raise ValueError("GPU compute requires vip tier (and manual approval)")
    lang = contract.get("output_language")
    if lang is not None and str(lang).lower() not in OUTPUT_LANGUAGES:
        raise ValueError(f"unsupported output_language: {lang!r} (zh | en)")


def journal_quartile(contract: dict[str, Any]) -> str | None:
    explicit = str(contract.get("target_journal_q") or "").strip().lower()
    if explicit in JOURNAL_Q_THRESHOLDS:
        return explicit
    target = str(contract.get("target_journal") or "").lower()
    for quartile in JOURNAL_Q_THRESHOLDS:
        if quartile in target.replace("-", " ").split():
            return quartile
    return None


def journal_needs_real_lane(contract: dict[str, Any]) -> bool:
    text = " ".join(
        str(contract.get(key) or "").lower()
        for key in ("topic", "research_question", "contribution")
    )
    experiment_markers = (
        "benchmark",
        "classification",
        "experiment",
        "empirical",
        "prediction",
        "real-data",
        "real data",
    )
    return any(marker in text for marker in experiment_markers)


def level_policy(contract: dict[str, Any]) -> dict[str, Any]:
    level = str(contract["level"])
    tier = str(contract["tier"])
    if level == "master":
        return {
            "content_threshold": LEVEL_THRESHOLDS["master"],
            "review_depth": "7dim",
            "model_policy": "free",
            "needs_real_experiment_lane": False,
            "elite_required": False,
            "elite_optional": True,
        }
    if level == "phd":
        return {
            "content_threshold": LEVEL_THRESHOLDS["phd"],
            "review_depth": "7dim+elite",
            "model_policy": "paid",
            "needs_real_experiment_lane": True,
            "elite_required": True,
            "elite_optional": False,
        }
    quartile = journal_quartile(contract)
    return {
        "content_threshold": JOURNAL_Q_THRESHOLDS.get(quartile or "", 7.0),
        "review_depth": "full-3-layer",
        "model_policy": "paid" if tier == "vip" else "free",
        "needs_real_experiment_lane": journal_needs_real_lane(contract),
        "elite_required": True,
        "elite_optional": False,
        "target_journal_q": quartile or "unspecified",
    }


def base_decision(contract: dict[str, Any]) -> dict[str, Any]:
    policy = level_policy(contract)
    decision = {
        "source": contract["source"],
        "tier": contract["tier"],
        "level": contract["level"],
        "output_language": str(contract.get("output_language") or "en").lower(),
        **policy,
    }
    if requested_compute(contract) == "gpu":
        # GPU never auto-runs: validate_contract already ensured tier=vip; the
        # job runner blocks the job and notifies — manual approval required.
        decision["needs_gpu"] = True
        decision["needs_manual_approval"] = True
    return decision


def route_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Return a routing decision consumed by the job runner."""
    validate_contract(contract)
    source = contract["source"]
    tier = contract["tier"]
    level = contract["level"]
    decision = base_decision(contract)
    if source == "paper-mcp" and level == "master":
        return {
            **decision,
            "lane": "mvp/CPU-real",
            "model_chain": ["big-pickle"],
            "driver": "hermes",
            # Reviewer chain: copilot when its quota is live; otherwise the skilled
            # big-pickle reviewer (verbatim-anchored tasks + floor-cross-checked
            # scores) iterates quality rounds — master converges in ~3.
            "reviewer_chain": ["copilot", "codex", "big-pickle-skilled", "deterministic_floor"],
            "max_revision_rounds": 3,
            "hooks": ["data_availability_gate", "paper_gate", "deterministic_content_review"],
            "timeout_seconds": 21600,
            "fallback_policy": {
                "paid_fallback": False,
                "max_attempts_per_model": 2,
                "fallback_on": ["retryable_runtime_error"],
            },
        }
    if source == "paper-mcp" and level == "phd":
        return {
            **decision,
            "lane": "phd/real-experiment",
            # phd certification is copilot-only (the skilled fallback may revise
            # but never certify an elite-required paper).
            "reviewer_chain": ["copilot", "codex", "deterministic_floor"],
            "max_revision_rounds": 2,
            # Route A: all lanes run on the Hermes phasefix driver + the free
            # big-pickle model (opencode Zen, no login/key). The hard DOI
            # anti-cheat gate (paper_driver.doi_gate) is what keeps the free
            # model honest, so no paid provider is needed.
            "model_chain": ["big-pickle"],
            "driver": "hermes",
            "hooks": ["data_availability_gate", "paper_gate", "deterministic_content_review", "elite_review"],
            "timeout_seconds": 21600,
            "fallback_policy": {
                "paid_fallback": True,
                "max_attempts_per_model": 1,
                "fallback_on": ["model_unavailable", "timeout", "nonzero_exit"],
            },
        }
    if source == "paper-mcp" and level == "journal":
        paid = decision["model_policy"] == "paid"
        return {
            **decision,
            "lane": "journal/real-experiment" if decision["needs_real_experiment_lane"] else "journal/literature",
            "reviewer_chain": ["copilot", "codex", "deterministic_floor"],
            "max_revision_rounds": 2,
            "model_chain": ["big-pickle"],
            "driver": "hermes",
            "hooks": ["data_availability_gate", "paper_gate", "deterministic_content_review", "elite_review"],
            "timeout_seconds": 21600,
            "fallback_policy": {
                "paid_fallback": paid,
                "max_attempts_per_model": 1 if paid else 2,
                "fallback_on": ["model_unavailable", "timeout", "nonzero_exit"] if paid else ["retryable_runtime_error"],
            },
        }
    raise ValueError(f"no route for source={source} tier={tier} level={level}")
