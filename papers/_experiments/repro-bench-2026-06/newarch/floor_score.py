"""Deterministic floor scoring — a model-free, conservative content score computed purely
from artifacts the pipeline already produces. Terminal reviewer tier: used when the model
reviewer (Copilot/Gemini) is unavailable, and always computed as a cross-check.

CRITICAL POLICY (do not regress): the floor makes a job a `done` DELIVERABLE but does NOT
certify it passed peer-style review. For journal/phd lanes `meets_threshold` stays driven
by a REAL model reviewer; the floor never flips a journal paper to "passed" on its own
(see compile_review: floor sets review_status=floor_only, provisional). The floor is a
floor, not an approval. `novelty` is NOT deterministically measurable and is excluded from
the mean (emitted as null) — never a fixed constant in a pass/fail decision.

Each dimension returns a score in [1.0, 10.0] plus the raw evidence so the number is
auditable. Mappings are intentionally conservative; thresholds are first-pass and flagged
for calibration against a labelled set of prior reviewed runs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FLOOR_DIMS = (
    "methodological_rigor", "evidence_validity", "literature_grounding",
    "result_interpretation", "limitation_honesty", "writing_coherence",
)  # novelty intentionally excluded — not deterministically measurable


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
    except (json.JSONDecodeError, OSError):
        return default


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore") if p.is_file() else ""
    except OSError:
        return ""


def _clamp(x: float) -> float:
    return round(max(1.0, min(10.0, x)), 2)


def hard_gates(run_dir: Path) -> dict[str, Any]:
    """Pre-conditions that must hold before any floor number is meaningful. A failing
    hard gate is surfaced (and already blocks elsewhere); the floor stays conservative."""
    rr = _read_json(run_dir / "real_experiments" / "real_results.json", {})
    consistency = _read_json(run_dir / "consistency_tasks.json", {})
    ctasks = consistency.get("tasks", []) if isinstance(consistency, dict) else []
    gates = {
        "real_completed": str(rr.get("status")) == "completed",
        "not_simulated": not bool(rr.get("simulated", False))
        and int(rr.get("simulation_markers") or 0) == 0,
        "no_consistency_p0": not any(
            isinstance(t, dict) and t.get("severity") == "P0" for t in ctasks
        ),
    }
    gates["all_pass"] = all(gates.values())
    return gates


def _evidence_validity(run_dir: Path, gates: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    cem = _read_text(run_dir / "claim_evidence_map.md")
    rows = [ln for ln in cem.splitlines() if ln.strip().startswith("|") and "PASS" in ln or
            (ln.strip().startswith("|") and re.search(r"\bFAIL\b", ln))]
    passes = len(re.findall(r"\bPASS\b", cem))
    fails = len(re.findall(r"(?<![A-Za-z])FAIL(?:ED)?\b", cem))
    total = passes + fails
    coverage = (passes / total) if total else 0.0
    # Coverage alone is gameable (few vague claims). Require the hard gates + a real
    # claim count; cap hard when gates fail or when there are suspiciously few claims.
    score = 3.0
    if total >= 8 and gates["all_pass"]:
        score = 4.5 + 3.0 * coverage  # 100% coverage, ≥8 claims, gates pass -> 7.5
    elif total >= 4 and gates["all_pass"]:
        score = 4.0 + 2.5 * coverage
    elif gates["all_pass"]:
        score = 3.5 + 1.5 * coverage
    if not gates["not_simulated"] or not gates["real_completed"]:
        score = min(score, 3.0)
    return _clamp(score), {"claims_pass": passes, "claims_fail": fails, "coverage": round(coverage, 3)}


def _literature_grounding(run_dir: Path) -> tuple[float, dict[str, Any]]:
    meta = _read_json(run_dir / "metadata.json", [])
    audit = _read_json(run_dir / "doi_audit.json", {})
    qmd = _read_text(run_dir / "paper_draft_v0.qmd")
    n_refs = len(meta) if isinstance(meta, list) else 0
    # verified rate: prefer the anti-cheat doi_audit, else metadata status field.
    real_rate = None
    if isinstance(audit, dict):
        real_rate = audit.get("real_rate") if isinstance(audit.get("real_rate"), (int, float)) else None
    if real_rate is None and isinstance(meta, list) and meta:
        ok = sum(1 for r in meta if isinstance(r, dict) and str(r.get("status") or "").lower()
                 in {"ok", "verified", "crossref_real"})
        real_rate = ok / len(meta) if meta else 0.0
    real_rate = float(real_rate) if real_rate is not None else 0.0
    cited = set(re.findall(r"@([A-Za-z][A-Za-z0-9_:-]+)", qmd))
    ref_keys = {r.get("key") for r in meta if isinstance(r, dict)} if isinstance(meta, list) else set()
    used_rate = (len(cited & ref_keys) / len(ref_keys)) if ref_keys else 0.0
    # base from count + verified rate; cap for citation-stuffing (refs not used in text)
    base = 3.0
    if n_refs >= 35:
        base = 6.5
    elif n_refs >= 25:
        base = 5.5
    elif n_refs >= 15:
        base = 4.5
    score = base * (0.5 + 0.5 * real_rate)          # unverified refs are worth little
    score *= (0.7 + 0.3 * min(1.0, used_rate / 0.8))  # penalise large unused bibliography
    return _clamp(score), {"n_refs": n_refs, "verified_rate": round(real_rate, 3),
                           "cited_in_text_rate": round(used_rate, 3)}


def _methodological_rigor(run_dir: Path) -> tuple[float, dict[str, Any]]:
    rr = _read_json(run_dir / "real_experiments" / "real_results.json", {})
    qmd = _read_text(run_dir / "paper_draft_v0.qmd").lower()
    checks = {
        "cross_validation": bool(rr.get("cv_requested")) or "cross-validation" in qmd or "5-fold" in qmd,
        "uncertainty_ci": bool(rr.get("bootstrap_samples")) or "confidence interval" in qmd or "bootstrap" in qmd,
        "significance_test": bool(rr.get("statistical_tests")) or "mcnemar" in qmd or "p-value" in qmd or "p =" in qmd,
        "ablation": bool(rr.get("ablations")) or "ablation" in qmd,
        "seed_provenance": rr.get("random_state") is not None or "random state" in qmd or "seed" in qmd,
        "baselines": (isinstance(rr.get("models"), list) and len(rr.get("models")) >= 3)
        or "baseline" in qmd,
        "leakage_split": "holdout" in qmd or "train" in qmd and "test" in qmd or "stratif" in qmd,
        "metric_appropriate": "macro-f1" in qmd or "macro f1" in qmd or "weighted" in qmd,
    }
    passed = sum(1 for v in checks.values() if v)
    score = 3.0 + (passed / len(checks)) * 5.0   # all 8 -> 8.0; conservative
    return _clamp(score), {"checks_passed": passed, "checks_total": len(checks),
                           "detail": {k: bool(v) for k, v in checks.items()}}


def _limitation_honesty(run_dir: Path) -> tuple[float, dict[str, Any]]:
    qmd = _read_text(run_dir / "paper_draft_v0.qmd")
    low = qmd.lower()
    has_section = bool(re.search(r"(?im)^#+\s*limitation", qmd)) or "limitations" in low
    # Require NAMED, real weaknesses — not just an empty/padded section.
    named = {
        "sample_size": "subset" in low or "sample size" in low or "single filing year" in low,
        "single_dataset": "single dataset" in low or "one dataset" in low or "may not generalis" in low or "may not generalize" in low,
        "classical_only": "cpu-only" in low or "no bert" in low or "transformer" in low and "do not" in low,
        "class_imbalance": "imbalance" in low,
        "non_significant": "not statistically significant" in low or "p > 0.05" in low or "non-significant" in low,
        "external_validity": "generalis" in low or "generalize" in low or "external valid" in low,
    }
    n_named = sum(1 for v in named.values() if v)
    score = 2.5
    if has_section:
        score = 4.0 + min(4.0, n_named * 0.8)   # section + several named real weaknesses -> ~8
    return _clamp(score), {"has_section": has_section, "named_weaknesses": n_named}


def _writing_coherence(run_dir: Path) -> tuple[float, dict[str, Any]]:
    # Presence/length are NOT coherence; keep this dim low-weight and CAPPED at 7.0.
    qmd = _read_text(run_dir / "paper_draft_v0.qmd")
    gate_d = _read_text(run_dir / "gate_d_readability.md")
    expected = ["introduction", "method", "result", "discussion", "conclusion"]
    low = qmd.lower()
    present = sum(1 for s in expected if s in low)
    readable_ok = "pass" in gate_d.lower() or "grade" in gate_d.lower()
    score = 3.5 + (present / len(expected)) * 2.5 + (1.0 if readable_ok else 0.0)
    return _clamp(min(score, 7.0)), {"sections_present": present, "readability_artifact": readable_ok}


def _result_interpretation(run_dir: Path) -> tuple[float, dict[str, Any]]:
    rr = _read_json(run_dir / "real_experiments" / "real_results.json", {})
    low = _read_text(run_dir / "paper_draft_v0.qmd").lower()
    has_stats = bool(rr.get("statistical_tests"))
    # Honest handling of non-significant results (no overclaiming) is the key signal.
    reports_nonsig = "not statistically significant" in low or "p > 0.05" in low or "non-significant" in low
    overclaim = bool(re.search(r"\b(proves?|definitively|always outperforms?|guarantee)\b", low))
    score = 4.0
    if has_stats:
        score += 1.5
    if reports_nonsig:
        score += 1.0
    if overclaim:
        score -= 1.5
    return _clamp(score), {"has_statistical_tests": has_stats, "reports_nonsignificant": reports_nonsig,
                           "overclaim_detected": overclaim}


def floor_scores(run_dir: Path) -> dict[str, Any]:
    """Compute the deterministic floor. Returns scores_7dim (novelty=None), mean over the
    6 measurable dims, per-dim evidence, the hard-gate status, and notes."""
    run_dir = Path(run_dir)
    gates = hard_gates(run_dir)
    ev, ev_e = _evidence_validity(run_dir, gates)
    lit, lit_e = _literature_grounding(run_dir)
    rig, rig_e = _methodological_rigor(run_dir)
    interp, interp_e = _result_interpretation(run_dir)
    lim, lim_e = _limitation_honesty(run_dir)
    coh, coh_e = _writing_coherence(run_dir)
    scores = {
        "methodological_rigor": rig, "evidence_validity": ev, "literature_grounding": lit,
        "result_interpretation": interp, "limitation_honesty": lim, "writing_coherence": coh,
        "novelty": None,
    }
    measurable = [scores[d] for d in FLOOR_DIMS]
    mean_6 = round(sum(measurable) / len(measurable), 2)
    return {
        "score_source": "deterministic_floor",
        "scores_7dim": scores,
        "mean_6_floor": mean_6,
        "novelty": None,
        "hard_gates": gates,
        "evidence": {
            "methodological_rigor": rig_e, "evidence_validity": ev_e,
            "literature_grounding": lit_e, "result_interpretation": interp_e,
            "limitation_honesty": lim_e, "writing_coherence": coh_e,
        },
        "notes": [
            "novelty excluded from mean (not deterministically measurable)",
            "floor is a delivery floor, NOT peer-review certification",
        ],
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(floor_scores(Path(sys.argv[1] if len(sys.argv) > 1 else ".")),
                     indent=2, ensure_ascii=False))
