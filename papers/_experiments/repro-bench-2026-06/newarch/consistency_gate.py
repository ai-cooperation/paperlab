#!/usr/bin/env python3
"""Engine C: deterministic consistency gate (Route A review loop).

Mechanically cross-checks the manuscript's claims against the REAL experiment
ground truth in real_results.json, and emits concrete, machine-verifiable edit
TASKS. Unlike the weak big-pickle reviewer, this is 100% reproducible and never
"misses" a flagged contradiction — it is the reliable TRIGGER + safety net that
stops false-passes (e.g. a paper claiming a multi-year temporal split on
single-year data).

No model, no network. Pure regex/number comparison.

Regexes follow the actual prose phrasing (verified against produced qmd, see
ENGINE_C_PLAN_REVIEW.md): year ranges use `--`, splits say "evaluating on" as
well as "testing on", and inner 3-fold CV must not be confused with outer 5-fold.

Output: consistency_tasks.json = {"tasks": [...], "summary": {...}}.
Usage: consistency_gate.py <run_dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

YEAR_RANGE = re.compile(r"20\d{2}\s*(?:--|[-–—])\s*20\d{2}")
SPLIT_CONTEXT = re.compile(
    r"(temporal holdout|train(?:ing|ed)?\s+on|evaluat(?:ing|ed?)\s+on|test(?:ing|ed?)\s+on)"
    r"[^.\n]{0,90}?(20\d{2})",
    re.IGNORECASE,
)
NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10,
}


def _load(run_dir: Path) -> tuple[dict[str, Any], str]:
    real = json.loads((run_dir / "real_experiments" / "real_results.json").read_text(encoding="utf-8"))
    qmd = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8", errors="ignore")
    return real, qmd


def ground_truth(real: dict[str, Any]) -> dict[str, Any]:
    bench = real.get("benchmark") if isinstance(real.get("benchmark"), list) else []
    n_classes = {r.get("task"): r.get("n_classes") for r in bench if isinstance(r, dict)}
    sci = real.get("scientometrics") or {}
    years = sci.get("filing_year_distribution") or {}
    return {
        "models": real.get("models") or [],
        "n_models": len(real.get("models") or []),
        "n_features": len(real.get("features") or []),
        "bootstrap_samples": real.get("bootstrap_samples"),
        "cv_folds": real.get("cv_requested"),
        "n_classes": n_classes,                       # {'acceptance':2,'cpc_section':7}
        "real_years": {str(y) for y in years.keys()}, # {'2016'}
    }


def _task(tid: str, severity: str, ttype: str, section: str, target: str, replacement: str,
          desc: str, grounding: str, absent: str | None = None, present: str | None = None,
          min_words: int = 3800, preserve_cites: bool = True) -> dict[str, Any]:
    return {
        "id": tid, "engine": "C", "severity": severity, "type": ttype,
        "target_section": section, "target_content": target, "replacement_content": replacement,
        "description": desc, "grounding": grounding,
        "verification": {"absent": absent, "present": present,
                         "min_words": min_words, "preserve_cites": preserve_cites},
    }


def _int_before(qmd: str, pattern: str) -> list[tuple[str, int]]:
    """Find (matched_text, integer) for '<N|word> <noun>' style claims."""
    out: list[tuple[str, int]] = []
    for m in re.finditer(pattern, qmd, re.IGNORECASE):
        tok = m.group(1).lower()
        n = int(tok) if tok.isdigit() else NUM_WORDS.get(tok)
        if n is not None:
            out.append((m.group(0), n))
    return out


def check_temporal(qmd: str, gt: dict[str, Any]) -> list[dict[str, Any]]:
    real_years = gt["real_years"] or {"2016"}
    mentioned = {m.group(2) for m in SPLIT_CONTEXT.finditer(qmd)}
    bad = mentioned - real_years
    has_range = bool(YEAR_RANGE.search(qmd))
    if not bad and not has_range:
        return []
    # capture the offending sentence as the rewrite target
    sent = next((s.strip() for s in re.split(r"(?<=[.])\s+", qmd)
                 if YEAR_RANGE.search(s) or (SPLIT_CONTEXT.search(s) and (set(re.findall(r"20\d{2}", s)) - real_years))),
                "the temporal holdout description")
    yr = ", ".join(sorted(real_years))
    return [_task(
        "DET-TEMPORAL-001", "P0", "block_rewrite", "Evaluation Protocol / Data",
        sent[:300],
        "",  # model supplies replacement for this block
        f"Manuscript describes a multi-year train/test split but the cohort is single-year ({yr}); "
        f"such a temporal split is impossible. Reframe as nested cross-validation on the {yr} cohort.",
        f"real_results.scientometrics.filing_year_distribution years = {sorted(real_years)}",
        absent=r"20\d{2}\s*(?:--|[-–—])\s*20\d{2}", present=r"cross-?validation",
    )]


def check_class_count(qmd: str, gt: dict[str, Any]) -> list[dict[str, Any]]:
    real_cpc = gt["n_classes"].get("cpc_section")
    if not isinstance(real_cpc, int):
        return []
    tasks: list[dict[str, Any]] = []
    for matched, n in _int_before(qmd, r"\b(\d{1,2}|two|three|four|five|six|seven|eight|nine|ten)[\s-]?class(?:es)?\b"):
        if "cpc" in qmd[max(0, qmd.find(matched) - 60): qmd.find(matched) + 60].lower() and n != real_cpc:
            tasks.append(_task(
                "DET-CPCCLASS-001", "P0", "value_swap", "Methodology / Results",
                matched, re.sub(r"\d{1,2}|two|three|four|five|six|seven|eight|nine|ten",
                                 str(real_cpc), matched, count=1, flags=re.IGNORECASE),
                f"CPC section task has {real_cpc} classes, not {n}.",
                f"real_results n_classes[cpc_section]={real_cpc}",
                absent=re.escape(matched), present=f"{real_cpc}",
            ))
    return tasks


def check_classifier_count(qmd: str, gt: dict[str, Any]) -> list[dict[str, Any]]:
    n = gt["n_models"]
    if not n:
        return []
    tasks: list[dict[str, Any]] = []
    # Require the word "classifiers" (the real error mode was "six classifiers").
    # Bare "N models" is excluded: "two models" is legitimate McNemar pairwise usage,
    # not a claim about the total classifier set (agy review §3, collateral risk).
    pat = r"\b(\d{1,2}|three|four|five|six|seven|eight|nine|ten)\s+(?:classical\s+|sklearn\s+|machine[\s-]learning\s+|ML\s+)?classifiers\b"
    for matched, claimed in _int_before(qmd, pat):
        if claimed != n:
            tasks.append(_task(
                "DET-NMODELS-001", "P0", "value_swap", "Methodology",
                matched, re.sub(r"\d{1,2}|two|three|four|five|six|seven|eight|nine|ten",
                                {5: "five"}.get(n, str(n)), matched, count=1, flags=re.IGNORECASE),
                f"The benchmark uses {n} classifiers ({', '.join(gt['models'])}), not {claimed}.",
                f"real_results models = {gt['models']}",
                absent=re.escape(matched),
            ))
    return tasks


def check_bootstrap(qmd: str, gt: dict[str, Any]) -> list[dict[str, Any]]:
    real_b = gt["bootstrap_samples"]
    if not isinstance(real_b, int):
        return []
    tasks: list[dict[str, Any]] = []
    for m in re.finditer(r"([\d,]{2,6})\s+bootstrap\s+(?:replicates|samples|resamples|iterations)", qmd, re.IGNORECASE):
        claimed = int(m.group(1).replace(",", ""))
        if claimed != real_b:
            tasks.append(_task(
                "DET-BOOTSTRAP-001", "P1", "value_swap", "Methodology",
                m.group(0), m.group(0).replace(m.group(1), str(real_b)),
                f"Bootstrap used {real_b} resamples, not {claimed}.",
                f"real_results.bootstrap_samples={real_b}",
                absent=re.escape(m.group(1)), present=str(real_b),
            ))
    return tasks


def run(run_dir: Path) -> dict[str, Any]:
    real, qmd = _load(run_dir)
    gt = ground_truth(real)
    raw: list[dict[str, Any]] = []
    for fn in (check_temporal, check_class_count, check_classifier_count, check_bootstrap):
        raw.extend(fn(qmd, gt))
    seen: set[tuple[str, str]] = set()
    tasks: list[dict[str, Any]] = []
    for t in raw:
        key = (t["id"], t["target_content"])
        if key not in seen:
            seen.add(key)
            tasks.append(t)
    summary = {
        "p0_tasks": sum(1 for t in tasks if t["severity"] == "P0"),
        "p1_tasks": sum(1 for t in tasks if t["severity"] == "P1"),
        "ground_truth": {k: gt[k] for k in ("n_models", "n_features", "bootstrap_samples", "cv_folds", "n_classes", "real_years")},
    }
    payload = {"tasks": tasks, "summary": summary}
    (run_dir / "consistency_tasks.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=list), encoding="utf-8")
    return payload


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: consistency_gate.py <run_dir>", file=sys.stderr)
        return 2
    payload = run(Path(argv[0]).resolve())
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=list))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
