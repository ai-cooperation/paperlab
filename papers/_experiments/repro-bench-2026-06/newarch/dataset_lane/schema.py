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
)
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
    """Every number the manuscript is allowed to cite, normalized to strings. The analysis
    script MUST emit `numeric_index` (a flat list/dict of its reported numbers); a paper
    number not in here is untraceable -> blocked."""
    idx = (real_results or {}).get("numeric_index")
    out: set[str] = set()
    vals = idx.values() if isinstance(idx, dict) else (idx or [])
    for v in vals:
        if isinstance(v, (int, float)):
            out.add(_norm_num(v))
        elif isinstance(v, str):
            out.add(v.strip())
    return out


def _norm_num(v: float) -> str:
    """Canonical numeric string so 1.20 and 1.2 match; integers stay integers."""
    f = float(v)
    if f == int(f):
        return str(int(f))
    return f"{f:.6g}"
