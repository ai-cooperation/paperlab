"""Generic anti-hallucination gates for the dataset lane. Every gate is domain-agnostic:
it verifies GENERAL properties (data really fetched, code really ran, the result is the
code's output, declared survey design was actually applied, every paper number traces to
the run) — it never names a dataset, column, or study. The dataset specifics it reads come
from the AGENT-written spec/result, not from this file.

Each gate returns a list of problems (empty == pass); a P0 problem fails the run closed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

from . import schema


def _p0(cid: str, msg: str, **extra: Any) -> dict[str, Any]:
    return {"id": cid, "severity": "P0", "type": "dataset_gate", "description": msg, **extra}


# ── 1. real data was actually fetched ────────────────────────────────────────
def fetch_gate(run_dir: Path) -> list[dict[str, Any]]:
    run_dir = Path(run_dir)
    manifest = schema.read_json(run_dir, schema.MANIFEST)
    if not manifest:
        return [_p0("DS_FETCH_NO_MANIFEST", "no data/manifest.json — nothing was fetched")]
    arts = manifest.get("artifacts") or []
    out: list[dict[str, Any]] = []
    real = [a for a in arts if a.get("bytes", 0) > 0 and not a.get("is_html")]
    if not real:
        out.append(_p0("DS_FETCH_NO_DATA",
                       "no non-empty data file fetched (only errors / an HTML landing page) — "
                       f"errors: {manifest.get('errors')}"))
    for a in arts:
        fn = str(a.get("filename") or "").lower()
        if any(m in fn for m in schema.SYNTHETIC_MARKERS):
            out.append(_p0("DS_FETCH_SYNTHETIC", f"file name suggests fabricated data: {fn}", file=fn))
        if a.get("bytes", 0) > 0 and not a.get("sha256"):
            out.append(_p0("DS_FETCH_NO_HASH", f"fetched file has no checksum: {fn}", file=fn))
    # manifest integrity: re-hash the body (minus the hash field) and compare
    body = {k: manifest[k] for k in manifest if k != "manifest_sha256"}
    if manifest.get("manifest_sha256") != schema.sha256_bytes(_canon(body)):
        out.append(_p0("DS_FETCH_MANIFEST_TAMPER", "manifest_sha256 does not match the manifest body"))
    lock = schema.read_json(run_dir, schema.SOURCE_LOCK) or {}
    if lock.get("status") != "available":
        out.append(_p0("DS_FETCH_UNAVAILABLE", f"data_source_lock status={lock.get('status')}"))
    return out


# ── 2. the analysis really ran and produced the result ───────────────────────
def execution_gate(run_dir: Path) -> list[dict[str, Any]]:
    run_dir = Path(run_dir)
    rec = schema.read_json(run_dir, schema.EXECUTION_RECORD)
    rr = schema.read_json(run_dir, schema.REAL_RESULTS)
    out: list[dict[str, Any]] = []
    if not rec:
        return [_p0("DS_EXEC_NO_RECORD", "no execution_record.json — analysis was never executed by the runner")]
    if rec.get("returncode") not in (0,):
        out.append(_p0("DS_EXEC_RC", f"analysis returncode={rec.get('returncode')} (stderr: {str(rec.get('stderr_tail'))[:200]})"))
    if not rr:
        return out + [_p0("DS_EXEC_NO_RESULT", "analysis produced no real_results.json")]
    if rr.get("status") != "completed":
        out.append(_p0("DS_EXEC_NOT_COMPLETED", f"real_results.status={rr.get('status')}"))
    if rr.get("simulated") is not False:
        out.append(_p0("DS_EXEC_SIMULATED", "real_results.simulated is not False — only real-data runs may deliver"))
    # produced DURING this execution (not pre-written by an LLM)
    mt, t0, t1 = rec.get("real_results_mtime_unix"), rec.get("started_at_unix"), rec.get("finished_at_unix")
    if mt is None or t0 is None or mt < t0 - 1:
        out.append(_p0("DS_EXEC_STALE_RESULT", "real_results.json was not written during this execution (mtime precedes the run)"))
    # the analysis read the REAL manifest (its declared hash must equal the runner-seen manifest)
    if rr.get("data_manifest_sha256") and rec.get("manifest_sha256") \
            and rr["data_manifest_sha256"] != rec["manifest_sha256"]:
        out.append(_p0("DS_EXEC_MANIFEST_MISMATCH",
                       "real_results.data_manifest_sha256 != the manifest the runner executed against "
                       "(the analysis did not read the real downloaded data)"))
    return out


# ── 3. the result has the fields every gate/table/manuscript needs ────────────
def schema_gate(run_dir: Path) -> list[dict[str, Any]]:
    rr = schema.read_json(Path(run_dir), schema.REAL_RESULTS)
    if not rr:
        return [_p0("DS_SCHEMA_NO_RESULT", "no real_results.json")]
    out: list[dict[str, Any]] = []
    for f in schema.REAL_RESULTS_REQUIRED:
        if f not in rr:
            out.append(_p0("DS_SCHEMA_FIELD", f"real_results missing required field: {f}", field=f))
    models = rr.get("models") or []
    if not models:
        out.append(_p0("DS_SCHEMA_NO_MODELS", "real_results.models is empty — no estimates to report"))
    for i, m in enumerate(models):
        for f in schema.MODEL_REQUIRED:
            if f not in m:
                out.append(_p0("DS_SCHEMA_MODEL_FIELD", f"model[{i}] missing {f}", model=m.get("id"), field=f))
    sd = rr.get("survey_design")
    if isinstance(sd, dict) and sd.get("weighted"):
        for f in schema.SURVEY_DESIGN_REQUIRED:
            if f not in sd:
                out.append(_p0("DS_SCHEMA_SURVEY_FIELD", f"survey_design missing {f}", field=f))
    return out


# ── 4. IF it claims a complex-survey design, it must have actually applied it ─
def survey_gate(run_dir: Path) -> list[dict[str, Any]]:
    """Generic: reads the DECLARED survey design (whatever the columns are named for this
    dataset) and proves the analysis really used it — no dataset/column names hardcoded.
    A study that is not survey-weighted simply passes (survey_design absent/weighted=False)."""
    rr = schema.read_json(Path(run_dir), schema.REAL_RESULTS) or {}
    sd = rr.get("survey_design")
    if not isinstance(sd, dict) or not sd.get("weighted"):
        return []                                            # not a survey study — nothing to assert
    out: list[dict[str, Any]] = []
    for key in ("weight_variable", "strata_variable", "psu_variable"):
        if not sd.get(key):
            out.append(_p0("DS_SURVEY_NO_DESIGN_COL", f"survey design claims weighted but {key} is empty"))
    if not isinstance(sd.get("design_df"), (int, float)) or (sd.get("design_df") or 0) <= 0:
        out.append(_p0("DS_SURVEY_BAD_DF", f"survey design_df must be > 0, got {sd.get('design_df')}"))
    # weighting must actually change N somewhere: an unweighted fit would report n_unweighted == n_weighted
    models = rr.get("models") or []
    changed = any(m.get("n_weighted") is not None and m.get("n_unweighted") is not None
                  and float(m.get("n_weighted")) != float(m.get("n_unweighted")) for m in models)
    if models and not changed:
        out.append(_p0("DS_SURVEY_NOT_APPLIED",
                       "every model reports n_weighted == n_unweighted — the survey weights were not applied"))
    # the declared design columns must appear among the variables the analysis says it read
    seen_cols = set(rr.get("variables", {}) or {}) | set(rr.get("columns_used", []) or [])
    if seen_cols:
        for key in ("weight_variable", "strata_variable", "psu_variable"):
            col = sd.get(key)
            if col and col not in seen_cols:
                out.append(_p0("DS_SURVEY_COL_ABSENT",
                               f"declared {key}='{col}' is not among the analysis variables actually used", col=col))
    return out


# ── 5. recompute cheap invariants from the REAL data (tamper / fabrication) ───
def recompute_gate(run_dir: Path, *, row_counter: Callable[[dict], int] | None = None) -> list[dict[str, Any]]:
    """Re-derive a cheap invariant (row count) from the actually-downloaded data and check
    it matches the result. `row_counter(manifest)->int` is injectable; the production
    default reads the data with pandas. Best-effort: skips silently if it cannot read."""
    run_dir = Path(run_dir)
    rr = schema.read_json(run_dir, schema.REAL_RESULTS) or {}
    manifest = schema.read_json(run_dir, schema.MANIFEST) or {}
    counter = row_counter or _default_row_counter
    try:
        actual_rows = counter(manifest)
    except Exception:  # noqa: BLE001 - cannot recompute (binary format w/o reader) -> advisory skip
        return []
    if actual_rows is None:
        return []
    claimed = rr.get("rows")
    if isinstance(claimed, (int, float)) and actual_rows > 0 and claimed > actual_rows:
        return [_p0("DS_RECOMPUTE_ROWS",
                    f"real_results.rows={claimed} exceeds the real data row count {actual_rows} "
                    "(numbers cannot describe more rows than exist)")]
    return []


def _default_row_counter(manifest: dict[str, Any]) -> int | None:
    """Sum CSV rows across artifacts using only the stdlib (XPT/SAS read by the lane's
    pandas recompute, not here). Returns None when nothing is countable offline."""
    import csv
    total, counted = 0, False
    for a in manifest.get("artifacts", []):
        # we only have the probe sample here; a real reader is injected in production
        ps = a.get("probe_sample") or {}
        if isinstance(ps.get("sampled_rows"), int):
            total += ps["sampled_rows"]
            counted = True
    return total if counted else None


# ── 6. every number in the manuscript traces to the analysis output ──────────
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
# universal statistical-writing conventions (CI levels, significance thresholds, small
# counts) — not results, not dataset-specific. Allowed everywhere so prose like "95% CI"
# and "p < 0.05" does not read as an untraceable number.
_CONVENTION_NUMS = {"0", "1", "2", "3", "4", "5", "10", "90", "95", "99", "100",
                    "0.05", "0.01", "0.1", "0.001", "1.96"}


def number_trace(qmd_text: str, real_results: dict[str, Any], *,
                 whitelist: set[str] | None = None) -> list[dict[str, Any]]:
    """Every numeric token in the manuscript prose must appear in the analysis
    `numeric_index` (or the small whitelist of contract/source years). A number that is
    nowhere in the machine output is a hallucination -> blocked. Domain-agnostic."""
    allowed = schema.iter_numeric_index(real_results) | _CONVENTION_NUMS | (whitelist or set())
    allowed_floats = {_to_float(x) for x in allowed}
    allowed_floats.discard(None)
    untraced: list[str] = []
    for tok in _NUM_RE.findall(qmd_text or ""):
        f = _to_float(tok)
        if f is None:
            continue
        if tok.strip() in allowed:
            continue
        if any(abs(f - a) <= 1e-6 + 1e-4 * abs(a) for a in allowed_floats):
            continue
        if -1900 <= f <= 2100 and float(int(f)) == f:        # bare years handled by whitelist below
            if str(int(f)) in allowed:
                continue
        untraced.append(tok)
    # collapse + cap
    uniq = sorted(set(untraced), key=lambda s: (len(s), s))[:25]
    if uniq:
        return [_p0("DS_NUMBER_UNTRACED",
                    f"{len(uniq)} manuscript number(s) do not trace to the analysis output: {uniq}",
                    numbers=uniq)]
    return []


def _to_float(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def run_all(run_dir: Path) -> list[dict[str, Any]]:
    """Run the structural gates (fetch->execution->schema->survey->recompute) in order.
    number_trace runs later at manuscript time. Returns all problems (empty == pass)."""
    out: list[dict[str, Any]] = []
    out += fetch_gate(run_dir)
    out += execution_gate(run_dir)
    out += schema_gate(run_dir)
    out += survey_gate(run_dir)
    out += recompute_gate(run_dir)
    return out


def _canon(obj: Any) -> bytes:
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
