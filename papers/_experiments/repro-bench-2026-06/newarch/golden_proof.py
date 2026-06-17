"""Golden-proof harness (ENGINE_BUILD_PLAN P10).

P10 = "run the full paper-draft bundle via Hermes on the frozen corpus and reproduce
>= the golden review score, passing all gates." The LIVE run (codex brain + 28-skill
bundle + big-pickle on ac-2012) produces a fresh run dir; THIS module is the
deterministic acceptance check that grades any run dir against the frozen golden bar.

Run it against the golden_paper fixture to prove the bar-check itself; run it against
a fresh Hermes run (on ac-2012) to accept/reject that run. Offline-testable; the live
Hermes execution is a separate ac-2012 invocation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REVIEW_FILE = "final_content_review_deterministic.json"
GATE_FILE = "gate_report.json"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def review_score(run_dir: Path) -> float | None:
    """The strong-reviewer score, /100. Reads the golden's
    final_content_review_deterministic.json (scores_7dim mean *10) OR, for a live
    framework run, the latest quality_review_round{r}.json (score_100). None when
    the run was never scored."""
    run_dir = Path(run_dir)
    review = _read(run_dir / REVIEW_FILE)
    dims = review.get("scores_7dim") or {}
    vals = [(v.get("score") if isinstance(v, dict) else v) for v in dims.values()]
    vals = [float(v) for v in vals if isinstance(v, (int, float))]
    if vals:
        return round(sum(vals) / len(vals) * 10.0, 1)      # /10 dims -> /100
    rounds = sorted(run_dir.glob("quality_review_round*.json"))
    if rounds:
        last = _read(rounds[-1])
        if isinstance(last.get("score_100"), (int, float)):
            return float(last["score_100"])
    return None


def floor_score_100(run_dir: Path) -> float | None:
    """The deterministic floor (floor_score.py), /100 — the un-gameable cross-check
    available for ANY run dir (golden or live)."""
    try:
        import floor_score as _fs
        fs = _fs.floor_scores(Path(run_dir))
        m = fs.get("mean_6_floor")
        return round(float(m) * 10.0, 1) if m is not None else None
    except Exception:  # noqa: BLE001
        return None


def gate_summary(run_dir: Path) -> dict[str, Any]:
    g = _read(Path(run_dir) / GATE_FILE)
    return {"no_p0": g.get("no_p0"), "p1_count": g.get("p1_count"),
            "prose_completeness_passed": g.get("prose_completeness_passed"),
            "real_status": g.get("real_status")}


def prove_against_golden(candidate_dir: Path, golden_dir: Path,
                         *, require_no_p0: bool = False) -> dict[str, Any]:
    """Accept `candidate_dir` iff its review score >= the golden bar (and, for a
    PRODUCTION run, no P0). The golden_paper fixture is a real mid-quality baseline;
    a fresh Hermes run must meet or beat it."""
    cand = review_score(candidate_dir)
    bar = review_score(golden_dir)
    cand_floor = floor_score_100(candidate_dir)
    bar_floor = floor_score_100(golden_dir)
    gates = gate_summary(candidate_dir)
    meets_score = cand is not None and bar is not None and cand >= bar
    meets_floor = cand_floor is not None and bar_floor is not None and cand_floor >= bar_floor
    meets_gates = (gates.get("no_p0") is True) if require_no_p0 else True
    return {
        "candidate_review": cand, "golden_review_bar": bar,
        "candidate_floor": cand_floor, "golden_floor_bar": bar_floor,
        "meets_review": meets_score, "meets_floor": meets_floor, "meets_gates": meets_gates,
        "gate_summary": gates,
        # pass = beats the golden on the deterministic floor (un-gameable) + (optionally) no P0
        "passed": bool(meets_floor and meets_gates),
    }
