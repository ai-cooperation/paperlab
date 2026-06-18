"""Shared contracts for the dataset lane — the SINGLE source of the run-dir layout, the
artifact schemas, and the field requirements every gate enforces. Domain-agnostic: this
file names no dataset, column, or study.

Run-dir layout the lane produces:
    data/
      raw/<filename>            real downloaded files (Python writes them, not the agent)
      manifest.json             provenance of every fetched artifact (+ manifest_sha256)
    data_source_lock.json       availability verdict (status + manifest_sha256)
    real_experiments/
      analysis_spec.json        AGENT-written: variables, models, survey design (per job)
      analysis.py               AGENT-written: the actual analysis code (per job)
      analysis_stdout.txt        captured
      analysis_stderr.txt        captured
      execution_record.json     DETERMINISTIC: hashes (script/spec/manifest/result) + rc + times
      real_results.json         produced BY analysis.py — every paper number traces here
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# ── run-dir paths (relative to run_dir) ──────────────────────────────────────
DATA_DIR = "data"
RAW_DIR = "data/raw"
MANIFEST = "data/manifest.json"
SOURCE_LOCK = "data_source_lock.json"
DOWNLOAD_PLAN = "data/download_plan.json"            # AGENT-written list of {url, filename}
EXP_DIR = "real_experiments"
ANALYSIS_SPEC = "real_experiments/analysis_spec.json"
ANALYSIS_CODE = "real_experiments/analysis.py"
ANALYSIS_STDOUT = "real_experiments/analysis_stdout.txt"
ANALYSIS_STDERR = "real_experiments/analysis_stderr.txt"
EXECUTION_RECORD = "real_experiments/execution_record.json"
REAL_RESULTS = "real_experiments/real_results.json"
FIX_PRESCRIPTION = "real_experiments/fix_prescription.md"   # BRAIN-written review of a failed run
SKILL_LESSON = "skill_lesson.json"                          # self-upgrade: distilled lesson

LANE_NAME = "dataset_agent_analysis"

# ── required fields (gates read these; one place to evolve the contract) ─────
REAL_RESULTS_REQUIRED = (
    "status", "simulated", "lane", "source",
    "data_manifest_sha256", "analysis_script_sha256",
    "rows", "sample_flow", "models", "numeric_index",
    # the analysis must DECLARE which model is primary — so the report card and the
    # research-value gate read a declaration, never guess the primary by string-matching
    # an id (that would be a fixed script wearing a general coat).
    "primary_model_id",
)
# research-value (Gate E, dataset lane): a finding — significant OR null — is worth writing
# only if the analysis is adequately POWERED. A well-powered null is informative; an
# underpowered one cannot conclude. Generic floors on the agent-produced n.
DATASET_N_FLOOR = 300       # analytic observations
DATASET_UNIT_FLOOR = 15     # distinct units (countries/subjects/...) for a panel/grouped design
# a model row must declare these so a gate can check it, regardless of the dataset
MODEL_REQUIRED = ("id", "family", "outcome", "exposure", "estimate", "n_unweighted")
# present ONLY when the analysis declares a complex-survey design (generic — no names)
SURVEY_DESIGN_REQUIRED = ("weighted", "weight_variable", "strata_variable",
                          "psu_variable", "design_df")
EXECUTION_RECORD_REQUIRED = (
    "analysis_script_sha256", "analysis_spec_sha256", "manifest_sha256",
    "real_results_sha256", "returncode", "started_at_unix", "finished_at_unix",
)
# filename substrings that betray fabricated/placeholder data (fail closed)
SYNTHETIC_MARKERS = ("synthetic", "simulated", "fake", "dummy", "example", "placeholder", "mock")


# ── shared result accessors (consumers read the DECLARATION, never guess) ────
def primary_model(rr: dict[str, Any]) -> dict[str, Any]:
    """The PRIMARY model — read from the analysis's declaration (`primary_model_id`),
    NOT guessed by string-matching ids. Falls back, for runs predating the declaration,
    to a heuristic (id/family naming the primary, then a fixed-effects/within spec, then
    the most-adjusted = most covariates), so old runs still render without breaking."""
    models = [m for m in (rr.get("models") or []) if isinstance(m, dict)]
    if not models:
        return {}
    declared = str(rr.get("primary_model_id") or "")
    if declared:
        for m in models:
            if str(m.get("id") or "") == declared:
                return m
    def _rank(m: dict[str, Any]) -> tuple:
        idf = (str(m.get("id") or "") + " " + str(m.get("family") or "")).lower()
        named = "primary" in idf
        fe = "fixed" in idf or "twfe" in idf or "within" in idf
        ncov = len(m.get("covariates") or []) + len(m.get("fixed_effects") or [])
        return (named, fe, ncov)
    return max(models, key=_rank)


def dataset_research_value(rr: dict[str, Any]) -> dict[str, Any]:
    """Gate E (dataset lane): is the finding worth writing? Value rests on POWER + a
    rigorous primary spec, NOT on getting a significant result — a well-powered null that
    qualifies a prior belief is valuable; an underpowered null cannot conclude. Returns
    {sufficient, rows, units, has_primary, reason}."""
    rows = int(rr.get("rows") or 0)
    sf = rr.get("sample_flow") or {}
    units = 0
    try:
        units = int(sf.get("analytic_units") or 0)
    except (TypeError, ValueError):
        units = 0
    if units == 0:
        for k, v in sf.items():
            if "countries" in k or "units" in k or "subjects" in k or "clusters" in k:
                try:
                    units = max(units, int(v))
                except (TypeError, ValueError):
                    pass
    unit_label = str(sf.get("unit_label") or "units")
    pm = primary_model(rr)
    has_primary = bool(pm)
    powered = rows >= DATASET_N_FLOOR and (units == 0 or units >= DATASET_UNIT_FLOOR)
    sufficient = powered and has_primary
    if sufficient:
        reason = (f"well-powered (n={rows}, {unit_label}={units}) with a primary specification — "
                  "the finding is informative whether or not it is statistically significant")
    elif not has_primary:
        reason = "no primary model specification declared"
    else:
        reason = (f"under-powered (n={rows}, {unit_label}={units}) — a null here cannot distinguish "
                  "'no association' from 'insufficient evidence'")
    return {"sufficient": sufficient, "rows": rows, "units": units,
            "has_primary": has_primary, "reason": reason}


# ── small deterministic helpers ──────────────────────────────────────────────
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(run_dir: Path, rel: str) -> Any:
    p = Path(run_dir) / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def write_json(run_dir: Path, rel: str, obj: Any) -> Path:
    p = Path(run_dir) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def iter_numeric_index(real_results: dict[str, Any]) -> set[str]:
    """Every number the manuscript is allowed to cite. ROBUST: walk the ENTIRE real_results
    (models, subgroup_results, sensitivity_results, spline_results, sample_flow, variables,
    AND the analysis's numeric_index) and collect every computed number — the actual results
    are the source of truth, not a self-reported index that the analysis may leave incomplete.
    A prose number not computed ANYWHERE is the fabrication this catches."""
    out: set[str] = set()

    def _walk(obj: Any) -> None:
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            out.add(_norm_num(float(obj)))
        elif isinstance(obj, str):
            s = obj.strip()
            if s:
                out.add(s)
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                _walk(v)

    _walk(real_results or {})
    return out


def _norm_num(v: float) -> str:
    """Canonical numeric string so 1.20 and 1.2 match; integers stay integers."""
    f = float(v)
    if f == int(f):
        return str(int(f))
    return f"{f:.6g}"
