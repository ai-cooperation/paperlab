#!/usr/bin/env python3
"""Compile the real 3-layer review reports into job_runner's scoring artifacts.

Replaces run_newarch.py's hardcoded 7-dim constants (the always-7.57 mock). The
scores here are whatever the review skills actually derived from the prose; this
module only parses and fails closed when a review did not emit usable scores. It
never invents a score.

Inputs (written by the review phases, each ending in a fenced ```json block):
- mvp_check_report.md     -> p0_count, p1_count, problems[]
- paper_review_report.md  -> scores_7dim{7 dimensions}
- elite_audit_report.md   -> desk_reject_probability   (optional)

Outputs (the contract job_runner.extract_output consumes):
- final_content_review_deterministic.json
- gate_report.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import floor_score
import tables

SEVEN_DIMS = (
    "novelty", "methodological_rigor", "evidence_validity", "literature_grounding",
    "result_interpretation", "limitation_honesty", "writing_coherence",
)
PROSE_WORD_FLOOR = 3000
# ALL-CAPS residue tokens match case-SENSITIVELY; lowercasing the text treated
# the ordinary word "placeholder" in honest disclosure prose as template
# residue (gate-manufactured unfixable finding, v3_bcee9fcada9f 2026-07-17).
# Same split as packs/paper/gates.py — keep the two in lockstep.
PLACEHOLDER_MARKERS_CASED = ("PLACEHOLDER", "<!-- PLACEHOLDER", "TODO:", "TBD")
PLACEHOLDER_MARKERS_ANYCASE = ("lorem ipsum",)


def _last_json_block(text: str) -> dict[str, Any] | None:
    """Return the last fenced ```json object in the markdown, or None."""
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if not blocks:
        blocks = re.findall(r"```\s*(\{.*?\})\s*```", text, re.DOTALL)
    for raw in reversed(blocks):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _read_block(run_dir: Path, name: str) -> dict[str, Any] | None:
    path = run_dir / name
    if not path.is_file():
        return None
    return _last_json_block(path.read_text(encoding="utf-8", errors="ignore"))


def _qmd_prose_words(run_dir: Path) -> int:
    qmd = run_dir / "paper_draft_v0.qmd"
    if not qmd.is_file():
        return 0
    text = qmd.read_text(encoding="utf-8", errors="ignore")
    # strip YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    # strip fenced code blocks
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    # CJK-aware: whitespace splitting undercounts Chinese by ~6x (a 6,000-char
    # zh paper counted 966 "words" and false-failed the 3,000 floor). Count CJK
    # chars separately at ~2 chars per word (conservative) + latin words.
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]", text))
    latin_words = len(re.sub(r"[\u4e00-\u9fff\u3400-\u4dbf]", " ", text).split())
    return latin_words + cjk // 2


def _has_placeholder(run_dir: Path) -> bool:
    qmd = run_dir / "paper_draft_v0.qmd"
    if not qmd.is_file():
        return True
    text = qmd.read_text(encoding="utf-8", errors="ignore")
    low = text.lower()
    return any(m in text for m in PLACEHOLDER_MARKERS_CASED) or any(
        m.lower() in low for m in PLACEHOLDER_MARKERS_ANYCASE
    )


def compile_reviews(run_dir: Path, content_threshold: float = 6.0, elite_required: bool = False) -> dict[str, Any]:
    run_dir = Path(run_dir).resolve()
    problems: list[dict[str, Any]] = []

    mvp = _read_block(run_dir, "mvp_check_report.md") or {}
    mvp_problems = mvp.get("problems") if isinstance(mvp.get("problems"), list) else []
    problems.extend(p for p in mvp_problems if isinstance(p, dict))

    # Merge Engine C deterministic consistency tasks (the reliable contradiction
    # detector). After a successful revision loop this file holds 0 P0; if a
    # contradiction was not fixed it remains here and correctly fails the gate.
    ctasks_path = run_dir / "consistency_tasks.json"
    if ctasks_path.is_file():
        try:
            ctasks = json.loads(ctasks_path.read_text(encoding="utf-8")).get("tasks", [])
        except (json.JSONDecodeError, AttributeError):
            ctasks = []
        for t in ctasks:
            if isinstance(t, dict):
                problems.append({
                    "id": t.get("id"), "severity": t.get("severity"),
                    "location": t.get("target_section"), "type": "consistency",
                    "description": t.get("description"),
                })

    # Render-quality issues (deterministic gate on the rendered PDF) — a broken
    # deliverable must not pass with a high content score.
    rq_path = run_dir / "render_quality.json"
    if rq_path.is_file():
        try:
            rq = json.loads(rq_path.read_text(encoding="utf-8")).get("issues", [])
        except (json.JSONDecodeError, AttributeError):
            rq = []
        problems.extend(i for i in rq if isinstance(i, dict))

    # Machine-owned GENERATED tables must still match real_results (tamper guard).
    problems.extend(tables.verify(run_dir))

    review = _read_block(run_dir, "paper_review_report.md") or {}
    raw_scores = review.get("scores_7dim") if isinstance(review.get("scores_7dim"), dict) else {}
    # The Copilot reviewer emits scores AND a task/problem list in paper_review_report.md.
    problems.extend(p for p in (review.get("problems") or []) if isinstance(p, dict))
    problems.extend(t for t in (review.get("tasks") or []) if isinstance(t, dict))
    scores: dict[str, float] = {}
    for dim in SEVEN_DIMS:
        try:
            scores[dim] = round(float(raw_scores[dim]), 2)
        except (KeyError, TypeError, ValueError):
            pass

    # Who produced the review? The copilot path and the skilled big-pickle
    # fallback both write paper_review_report.md; reviewer_status.json marks
    # the fallback so its scores face a HARD floor cross-check (the free model
    # is a known score hallucinator — divergent scores are rejected, not flagged).
    rstatus_early: dict[str, Any] = {}
    rspath = run_dir / "reviewer_status.json"
    if rspath.is_file():
        try:
            rstatus_early = json.loads(rspath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            rstatus_early = {}
    fallback_reviewer = rstatus_early.get("source") == "big-pickle-skilled"

    reviewer_unavailable = False
    score_source = "model_reviewer"
    review_status = "scored"
    floor: dict[str, Any] = {}
    if len(scores) == len(SEVEN_DIMS):
        mean_7dim = round(sum(scores.values()) / len(SEVEN_DIMS), 2)
        # Cross-check: compute the deterministic floor and compare measurable dims
        # (a large gap signals the model reviewer hallucinated a score).
        floor = floor_score.floor_scores(run_dir)
        floor_div = {
            d: round(scores[d] - floor["scores_7dim"][d], 2)
            for d in floor_score.FLOOR_DIMS
            if isinstance(floor["scores_7dim"].get(d), (int, float)) and d in scores
            and abs(scores[d] - floor["scores_7dim"][d]) > 2.5
        }
        if floor_div and fallback_reviewer:
            # Fallback reviewer failing the cross-check loses scoring rights
            # entirely — fall through to the deterministic floor.
            problems.append({
                "id": "FALLBACK_SCORE_REJECTED", "severity": "P1", "location": "review",
                "type": "model_floor_divergence",
                "description": f"fallback reviewer score diverges >2.5 from floor on {floor_div} "
                               "— scores rejected, deterministic floor used instead.",
            })
            scores = {}
        elif fallback_reviewer:
            score_source = "model_fallback_bigpickle"
            review_status = "scored_fallback"
        elif floor_div:
            problems.append({
                "id": "SCORE_DIVERGENCE", "severity": "P1", "location": "review",
                "type": "model_floor_divergence",
                "description": f"model score diverges >2.5 from deterministic floor on {floor_div} "
                               "— possible reviewer hallucination; verify.",
            })
    if len(scores) != len(SEVEN_DIMS):
        # Model reviewer produced no usable 7-dim score. Fall back to the deterministic
        # FLOOR (model-free, conservative). The floor delivers a `done` paper WITH a
        # provisional score, but does NOT certify peer-review pass: meets_threshold stays
        # False for any lane (see below) — a real reviewer is still required to certify.
        rstatus: dict[str, Any] = {}
        rpath = run_dir / "reviewer_status.json"
        if rpath.is_file():
            try:
                rstatus = json.loads(rpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                rstatus = {}
        reviewer_unavailable = rstatus.get("status") == "unavailable"
        floor = floor_score.floor_scores(run_dir)
        scores = {d: floor["scores_7dim"][d] for d in SEVEN_DIMS
                  if isinstance(floor["scores_7dim"].get(d), (int, float))}
        mean_7dim = floor["mean_6_floor"]
        score_source = "deterministic_floor"
        review_status = "floor_only"
        reason = rstatus.get("reason") or ("incomplete_review" if not reviewer_unavailable else "unknown")
        problems.append({
            "id": "REVIEWER_FLOOR", "severity": "INFO", "location": "reviewer_status.json",
            "type": "deterministic_floor_score",
            "description": f"Model reviewer unavailable (reason={reason}); scored by deterministic floor "
                           f"(mean_6={floor['mean_6_floor']}, gates={floor['hard_gates']['all_pass']}). "
                           "Delivered as a done paper but NOT certified — real reviewer still required.",
        })

    # desk_reject_probability may come from the elite audit OR the copilot review block.
    desk_reject = None
    for src in (_read_block(run_dir, "elite_audit_report.md") or {}, review):
        try:
            desk_reject = round(float(src["desk_reject_probability"]), 3)
            break
        except (KeyError, TypeError, ValueError):
            continue
    if desk_reject is None and elite_required:
        problems.append({
            "id": "ELITE_INCOMPLETE", "severity": "P1", "location": "review",
            "type": "missing_desk_reject_probability",
            "description": "no reviewer emitted desk_reject_probability.",
        })

    prose_words = _qmd_prose_words(run_dir)
    has_placeholder = _has_placeholder(run_dir)
    prose_ok = prose_words >= PROSE_WORD_FLOOR and not has_placeholder
    if not prose_ok:
        problems.append({
            "id": "PROSE_SKELETON", "severity": "P0", "location": "paper_draft_v0.qmd",
            "type": "incomplete_prose",
            "description": f"prose_total_words={prose_words} (floor {PROSE_WORD_FLOOR}), placeholder={has_placeholder}.",
        })

    real = {}
    real_path = run_dir / "real_experiments" / "real_results.json"
    if real_path.is_file():
        try:
            real = json.loads(real_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            real = {}
    real_status = real.get("status") or "not_run"

    p0_count = sum(1 for p in problems if p.get("severity") == "P0")
    p1_count = sum(1 for p in problems if p.get("severity") == "P1")

    # A deterministic-floor score delivers a `done` paper but NEVER certifies peer-review
    # pass — meets_threshold requires a real model reviewer. Floor only certifies that the
    # hard gates held; certification waits for a model score.
    if score_source == "deterministic_floor":
        meets_threshold = False
    elif score_source == "model_fallback_bigpickle" and elite_required:
        # The skilled fallback may certify MASTER-tier papers (cross-checked
        # against the floor); phd/journal certification waits for copilot.
        meets_threshold = False
    else:
        meets_threshold = bool(mean_7dim is not None and p0_count == 0 and mean_7dim >= content_threshold)
    final_review = {
        "mean_7dim": mean_7dim,
        "scores_7dim": scores,
        "p0_count": p0_count,
        "p1_count": p1_count,
        "problems": problems,
        "elite": {"desk_reject_probability": desk_reject},
        "content_threshold": content_threshold,
        "reviewer_unavailable": reviewer_unavailable,
        "score_source": score_source,
        "review_status": review_status,
        "floor_cross_check": floor.get("mean_6_floor") if isinstance(floor, dict) else None,
        "hard_gates_pass": floor.get("hard_gates", {}).get("all_pass") if isinstance(floor, dict) else None,
        "meets_threshold": meets_threshold,
    }
    (run_dir / "final_content_review_deterministic.json").write_text(
        json.dumps(final_review, indent=2, ensure_ascii=False), encoding="utf-8")

    gate_report = {
        "no_p0": p0_count == 0,
        "p1_count": p1_count,
        "no_prose_skeleton": not has_placeholder,
        "prose_completeness_passed": prose_words >= PROSE_WORD_FLOOR,
        "prose_total_words": prose_words,
        "real_status": real_status,
        "score_threshold": mean_7dim,
        "desk_reject_probability": desk_reject,
    }
    (run_dir / "gate_report.json").write_text(
        json.dumps(gate_report, indent=2, ensure_ascii=False), encoding="utf-8")

    return final_review


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: compile_review.py <run_dir> [content_threshold] [elite_required]", file=sys.stderr)
        return 2
    run_dir = Path(argv[0])
    threshold = float(argv[1]) if len(argv) > 1 else 6.0
    elite = argv[2].lower() in {"1", "true", "yes"} if len(argv) > 2 else False
    summary = compile_reviews(run_dir, threshold, elite)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
