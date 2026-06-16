"""Trust core of the GENERAL dataset lane (dataset_lane/*). The whole point is that the
engine is general, not a fixed script — so these tests use ARBITRARY made-up datasets and
column names (never NHANES) and prove the gates verify GENERAL properties: data really
fetched, code really ran, the declared survey design was actually applied, every number
traces. If any gate needed a specific dataset's names, these tests would not pass.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from dataset_lane import fetch, gates, runner, schema

pytestmark = pytest.mark.unit


# ── builders for a VALID run dir (arbitrary fictional dataset) ────────────────
def _good_manifest(run_dir: Path) -> dict:
    (run_dir / schema.RAW_DIR).mkdir(parents=True, exist_ok=True)
    (run_dir / schema.RAW_DIR / "core.csv").write_bytes(b"a,b\n1,2\n3,4\n")
    body = {"data_source": {"type": "dataset", "name": "Fictional Open Survey 2020"},
            "artifacts": [{"filename": "core.csv", "bytes": 12, "sha256": "x" * 64,
                           "is_html": False, "detected_format": "csv",
                           "probe_sample": {"readable": True, "sampled_rows": 2, "columns": ["a", "b"]}}],
            "errors": [], "n_files": 1}
    body["manifest_sha256"] = schema.sha256_bytes(gates._canon(body))
    schema.write_json(run_dir, schema.MANIFEST, body)
    schema.write_json(run_dir, schema.SOURCE_LOCK,
                      {"status": "available", "manifest_sha256": body["manifest_sha256"], "n_files": 1})
    return body


def _good_result(run_dir: Path, *, survey: bool = True) -> dict:
    rr = {
        "status": "completed", "simulated": False, "lane": schema.LANE_NAME,
        "source": "Fictional Open Survey 2020",
        "data_manifest_sha256": "MANIFEST_HASH", "analysis_script_sha256": "SCRIPT_HASH",
        "rows": 2, "sample_flow": {"start": 2, "analytic": 2},
        "variables": {"WIN_HRS": {}, "OUTCOME_X": {}, "MYWEIGHT": {}, "MYSTRATA": {}, "MYPSU": {}},
        "models": [{"id": "m1", "family": "survey_logistic", "outcome": "OUTCOME_X",
                    "exposure": "WIN_HRS", "estimate": 1.12, "ci_low": 1.01, "ci_high": 1.24,
                    "p_value": 0.03, "n_unweighted": 1234, "n_weighted": 1.2e8}],
        "numeric_index": [1.12, 1.01, 1.24, 0.03, 1234],
    }
    if survey:
        rr["survey_design"] = {"weighted": True, "weight_variable": "MYWEIGHT",
                               "strata_variable": "MYSTRATA", "psu_variable": "MYPSU", "design_df": 42}
    schema.write_json(run_dir, schema.REAL_RESULTS, rr)
    return rr


def _good_record(run_dir: Path) -> dict:
    out = run_dir / schema.REAL_RESULTS
    rec = {"analysis_script_sha256": "SCRIPT_HASH", "analysis_spec_sha256": "SPEC_HASH",
           "manifest_sha256": "MANIFEST_HASH", "real_results_sha256": "R_HASH",
           "real_results_mtime_unix": out.stat().st_mtime, "returncode": 0,
           "started_at_unix": out.stat().st_mtime - 5, "finished_at_unix": out.stat().st_mtime,
           "stdout_path": schema.ANALYSIS_STDOUT, "stderr_path": schema.ANALYSIS_STDERR}
    schema.write_json(run_dir, schema.EXECUTION_RECORD, rec)
    return rec


@pytest.fixture
def good(tmp_path):
    _good_manifest(tmp_path)
    _good_result(tmp_path)
    _good_record(tmp_path)
    return tmp_path


# ── fetch_gate ───────────────────────────────────────────────────────────────
def test_fetch_gate_passes_on_real_data(good):
    assert gates.fetch_gate(good) == []


def test_fetch_gate_blocks_html_only(tmp_path):
    body = {"artifacts": [{"filename": "page.html", "bytes": 500, "sha256": "y" * 64, "is_html": True}],
            "errors": [], "n_files": 1, "data_source": {}}
    body["manifest_sha256"] = schema.sha256_bytes(gates._canon(body))
    schema.write_json(tmp_path, schema.MANIFEST, body)
    schema.write_json(tmp_path, schema.SOURCE_LOCK, {"status": "unavailable"})
    ids = {p["id"] for p in gates.fetch_gate(tmp_path)}
    assert "DS_FETCH_NO_DATA" in ids


def test_fetch_gate_blocks_synthetic_filename(good):
    m = schema.read_json(good, schema.MANIFEST)
    m["artifacts"][0]["filename"] = "synthetic_data.csv"
    m["manifest_sha256"] = schema.sha256_bytes(gates._canon({k: m[k] for k in m if k != "manifest_sha256"}))
    schema.write_json(good, schema.MANIFEST, m)
    assert any(p["id"] == "DS_FETCH_SYNTHETIC" for p in gates.fetch_gate(good))


def test_fetch_gate_blocks_manifest_tamper(good):
    m = schema.read_json(good, schema.MANIFEST)
    m["artifacts"][0]["bytes"] = 999999          # edit body without recomputing the hash
    schema.write_json(good, schema.MANIFEST, m)
    assert any(p["id"] == "DS_FETCH_MANIFEST_TAMPER" for p in gates.fetch_gate(good))


# ── execution_gate ───────────────────────────────────────────────────────────
def test_execution_gate_passes(good):
    assert gates.execution_gate(good) == []


def test_execution_gate_blocks_simulated(good):
    rr = schema.read_json(good, schema.REAL_RESULTS); rr["simulated"] = True
    schema.write_json(good, schema.REAL_RESULTS, rr)
    assert any(p["id"] == "DS_EXEC_SIMULATED" for p in gates.execution_gate(good))


def test_execution_gate_blocks_stale_result(good):
    rec = schema.read_json(good, schema.EXECUTION_RECORD)
    rec["started_at_unix"] = rec["real_results_mtime_unix"] + 100   # result predates the run
    schema.write_json(good, schema.EXECUTION_RECORD, rec)
    assert any(p["id"] == "DS_EXEC_STALE_RESULT" for p in gates.execution_gate(good))


def test_execution_gate_blocks_manifest_mismatch(good):
    rr = schema.read_json(good, schema.REAL_RESULTS); rr["data_manifest_sha256"] = "WRONG"
    schema.write_json(good, schema.REAL_RESULTS, rr)
    assert any(p["id"] == "DS_EXEC_MANIFEST_MISMATCH" for p in gates.execution_gate(good))


def test_execution_gate_blocks_nonzero_rc(good):
    rec = schema.read_json(good, schema.EXECUTION_RECORD); rec["returncode"] = 1
    schema.write_json(good, schema.EXECUTION_RECORD, rec)
    assert any(p["id"] == "DS_EXEC_RC" for p in gates.execution_gate(good))


# ── survey_gate — GENERIC, arbitrary column names, never NHANES ──────────────
def test_survey_gate_passes_with_arbitrary_column_names(good):
    assert gates.survey_gate(good) == []          # MYWEIGHT/MYSTRATA/MYPSU — no hardcoded names


def test_survey_gate_non_survey_study_passes(tmp_path):
    _good_result(tmp_path, survey=False)
    assert gates.survey_gate(tmp_path) == []


def test_survey_gate_blocks_unapplied_weights(good):
    rr = schema.read_json(good, schema.REAL_RESULTS)
    rr["models"][0]["n_weighted"] = rr["models"][0]["n_unweighted"]   # weighting changed nothing
    schema.write_json(good, schema.REAL_RESULTS, rr)
    assert any(p["id"] == "DS_SURVEY_NOT_APPLIED" for p in gates.survey_gate(good))


def test_survey_gate_blocks_bad_design_df(good):
    rr = schema.read_json(good, schema.REAL_RESULTS); rr["survey_design"]["design_df"] = 0
    schema.write_json(good, schema.REAL_RESULTS, rr)
    assert any(p["id"] == "DS_SURVEY_BAD_DF" for p in gates.survey_gate(good))


def test_survey_gate_blocks_declared_col_not_used(good):
    rr = schema.read_json(good, schema.REAL_RESULTS)
    rr["survey_design"]["weight_variable"] = "NEVER_READ"
    schema.write_json(good, schema.REAL_RESULTS, rr)
    assert any(p["id"] == "DS_SURVEY_COL_ABSENT" for p in gates.survey_gate(good))


# ── schema_gate ──────────────────────────────────────────────────────────────
def test_schema_gate_passes(good):
    assert gates.schema_gate(good) == []


def test_schema_gate_blocks_missing_models(good):
    rr = schema.read_json(good, schema.REAL_RESULTS); rr["models"] = []
    schema.write_json(good, schema.REAL_RESULTS, rr)
    assert any(p["id"] == "DS_SCHEMA_NO_MODELS" for p in gates.schema_gate(good))


# ── number_trace ─────────────────────────────────────────────────────────────
def test_number_trace_passes_when_all_traced(good):
    rr = schema.read_json(good, schema.REAL_RESULTS)
    qmd = "The pooled odds ratio was 1.12 (95% CI 1.01 to 1.24, p = 0.03), n = 1234."
    assert gates.number_trace(qmd, rr) == []


def test_number_trace_blocks_untraced_number(good):
    rr = schema.read_json(good, schema.REAL_RESULTS)
    qmd = "The effect was 1.12 but we also claim a magic 7.77 that is nowhere in the output."
    probs = gates.number_trace(qmd, rr)
    assert probs and "7.77" in probs[0]["numbers"]


# ── fetch() + runner() with injected IO (no network / no subprocess) ─────────
def test_fetch_records_real_bytes_from_injected_downloader(tmp_path):
    schema.write_json(tmp_path, schema.DOWNLOAD_PLAN,
                      [{"url": "https://example.org/core.csv", "filename": "core.csv"}])

    def fake_dl(url, dest, timeout):
        data = b"x,y\n1,2\n"
        dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)
        return {"source_url": url, "filename": dest.name, "bytes": len(data),
                "sha256": schema.sha256_bytes(data), "is_html": False, "detected_format": "csv",
                "probe_sample": {"readable": True, "sampled_rows": 1, "columns": ["x", "y"]}}

    m = fetch.fetch(tmp_path, {"data_source": {"name": "D"}}, downloader=fake_dl)
    assert m["n_files"] == 1 and m["artifacts"][0]["sha256"]
    assert gates.fetch_gate(tmp_path) == []


def test_runner_records_execution(tmp_path):
    (tmp_path / schema.EXP_DIR).mkdir(parents=True, exist_ok=True)
    (tmp_path / schema.ANALYSIS_CODE).write_text("print('ran')\n", encoding="utf-8")
    (tmp_path / schema.ANALYSIS_SPEC).write_text("{}", encoding="utf-8")
    schema.write_json(tmp_path, schema.MANIFEST, {"manifest_sha256": "m"})

    def fake_run(cmd, rd):
        (Path(rd) / schema.REAL_RESULTS).write_text(json.dumps({"status": "completed"}), encoding="utf-8")
        return 0, "ran", ""

    rec = runner.run_analysis(tmp_path, runner_fn=fake_run)
    assert rec["returncode"] == 0 and rec["real_results_sha256"]
    assert (tmp_path / schema.EXECUTION_RECORD).is_file()
