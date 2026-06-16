"""The lane orchestration (dataset_lane/lane.py) with stubbed agent. Proves the control
flow: resolve->fetch->spec->code->execute->gates, the heal loop on gate failure, and that
a clean agent yields ok=True — all with a FICTIONAL dataset (no NHANES, no real network).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dataset_lane import gates, lane, schema

pytestmark = pytest.mark.unit


def _write_plan_and_data(run_dir: Path):
    schema.write_json(run_dir, schema.DOWNLOAD_PLAN,
                      [{"url": "https://example.org/core.csv", "filename": "core.csv"}])
    (run_dir / schema.RAW_DIR).mkdir(parents=True, exist_ok=True)
    (run_dir / schema.RAW_DIR / "core.csv").write_bytes(b"W,S,P,x,y\n1,1,1,2,3\n")


def _good_real_results(run_dir: Path) -> dict:
    manifest = schema.read_json(run_dir, schema.MANIFEST) or {}
    return {
        "status": "completed", "simulated": False, "lane": schema.LANE_NAME, "source": "Fict",
        "data_manifest_sha256": manifest.get("manifest_sha256"),
        "analysis_script_sha256": "S", "rows": 1, "sample_flow": {"start": 1, "analytic": 1},
        "variables": {"WCOL": {}, "SCOL": {}, "PCOL": {}, "x": {}, "y": {}},
        "survey_design": {"weighted": True, "weight_variable": "WCOL", "strata_variable": "SCOL",
                          "psu_variable": "PCOL", "design_df": 30},
        "models": [{"id": "m1", "family": "survey_logistic", "outcome": "y", "exposure": "x",
                    "estimate": 1.4, "ci_low": 1.1, "ci_high": 1.8, "p_value": 0.01,
                    "n_unweighted": 100, "n_weighted": 5000.0}],
        "numeric_index": [1.4, 1.1, 1.8, 0.01, 100],
    }


def _build_good_manifest(run_dir: Path) -> dict:
    body = {"data_source": {"name": "Fict"},
            "artifacts": [{"filename": "core.csv", "bytes": 20, "sha256": "z" * 64, "is_html": False,
                           "detected_format": "csv",
                           "probe_sample": {"readable": True, "sampled_rows": 1, "columns": ["W", "S", "P", "x", "y"]}}],
            "errors": [], "n_files": 1}
    body["manifest_sha256"] = schema.sha256_bytes(gates._canon(body))
    schema.write_json(run_dir, schema.MANIFEST, body)
    schema.write_json(run_dir, schema.SOURCE_LOCK, {"status": "available", "manifest_sha256": body["manifest_sha256"]})
    return body


def test_lane_happy_path_yields_ok(tmp_path, monkeypatch):
    calls = {"brain": 0, "worker": 0}

    def brain(prompt, writes):
        calls["brain"] += 1
        if schema.DOWNLOAD_PLAN in writes:
            schema.write_json(tmp_path, schema.DOWNLOAD_PLAN, [{"url": "u", "filename": "core.csv"}])
        elif schema.ANALYSIS_SPEC in writes:
            schema.write_json(tmp_path, schema.ANALYSIS_SPEC, {"survey": True})
        return True

    def worker(prompt, writes):                              # the WORKER drafts the analysis code
        calls["worker"] += 1
        if schema.ANALYSIS_CODE in writes:
            (tmp_path / schema.ANALYSIS_CODE).write_text("# analysis", encoding="utf-8")
        return True

    # stub the deterministic fetch (no network) + runner (no subprocess)
    def fake_fetch(rd, contract, **kw):
        return _build_good_manifest(Path(rd))

    def fake_runner(rd, **kw):
        schema.write_json(rd, schema.REAL_RESULTS, _good_real_results(rd))
        out = Path(rd) / schema.REAL_RESULTS
        rec = {"analysis_script_sha256": "S",
               "manifest_sha256": (schema.read_json(rd, schema.MANIFEST) or {}).get("manifest_sha256"),
               "real_results_sha256": "R", "real_results_mtime_unix": out.stat().st_mtime,
               "returncode": 0, "started_at_unix": out.stat().st_mtime - 1,
               "finished_at_unix": out.stat().st_mtime}
        schema.write_json(rd, schema.EXECUTION_RECORD, rec)
        return rec

    monkeypatch.setattr(lane.fetch, "fetch", fake_fetch)
    monkeypatch.setattr(lane.runner, "run_analysis", fake_runner)
    res = lane.run(tmp_path, {"data_source": {"type": "dataset", "url": "u", "name": "Fict"}},
                   brain=brain, worker=worker, max_heal_rounds=1)

    assert res["ok"] is True and res["problems"] == []
    assert res["real_results"]["models"][0]["estimate"] == 1.4
    assert calls["brain"] >= 2 and calls["worker"] >= 1    # brain: resolve+spec; worker: drafts code
    assert "history" in res                                 # two-layer loop records its rounds


def test_two_layer_heal_brain_reviews_worker_applies(tmp_path, monkeypatch):
    """The Hermes two-layer loop: worker drafts -> gate fails -> BRAIN reviews+prescribes ->
    WORKER applies -> gate passes. Both layers are exercised; the brain does not write code."""
    seen = {"review": 0, "apply": 0, "rounds": 0}

    def brain(prompt, writes):
        if schema.DOWNLOAD_PLAN in writes:
            schema.write_json(tmp_path, schema.DOWNLOAD_PLAN, [{"url": "u", "filename": "c.csv"}])
        elif schema.ANALYSIS_SPEC in writes:
            schema.write_json(tmp_path, schema.ANALYSIS_SPEC, {})
        elif schema.FIX_PRESCRIPTION in writes:            # BRAIN review -> prescription
            seen["review"] += 1
            (tmp_path / schema.FIX_PRESCRIPTION).write_text("apply the survey weights", encoding="utf-8")
        return True

    def worker(prompt, writes):
        if schema.ANALYSIS_CODE in writes:
            (tmp_path / schema.ANALYSIS_CODE).write_text("# code", encoding="utf-8")
            if (tmp_path / schema.FIX_PRESCRIPTION).is_file():
                seen["apply"] += 1                          # WORKER applied a prescription
        return True

    def fake_fetch(rd, contract, **kw):
        return _build_good_manifest(Path(rd))

    def fake_runner(rd, **kw):
        seen["rounds"] += 1
        rr = _good_real_results(Path(rd))
        if seen["rounds"] == 1:
            rr["models"] = []                               # first run: gate fails (no models)
        schema.write_json(rd, schema.REAL_RESULTS, rr)
        out = Path(rd) / schema.REAL_RESULTS
        schema.write_json(rd, schema.EXECUTION_RECORD,
                          {"analysis_script_sha256": "S",
                           "manifest_sha256": (schema.read_json(rd, schema.MANIFEST) or {}).get("manifest_sha256"),
                           "real_results_sha256": "R", "real_results_mtime_unix": out.stat().st_mtime,
                           "returncode": 0, "started_at_unix": out.stat().st_mtime - 1,
                           "finished_at_unix": out.stat().st_mtime})
        return {}

    monkeypatch.setattr(lane.fetch, "fetch", fake_fetch)
    monkeypatch.setattr(lane.runner, "run_analysis", fake_runner)
    res = lane.run(tmp_path, {"data_source": {"type": "dataset", "url": "u", "name": "Fict"}},
                   brain=brain, worker=worker, max_heal_rounds=2)
    assert res["ok"] is True
    assert seen["review"] >= 1 and seen["apply"] >= 1       # brain reviewed, worker applied
    assert seen["rounds"] >= 2                              # failed once, fixed, passed


def test_skill_upgrade_distils_and_persists(tmp_path):
    from dataset_lane import skill_upgrade
    bundle = tmp_path / "bundle"
    (bundle / "dataset-fetch").mkdir(parents=True)
    (bundle / "dataset-fetch" / "SKILL.md").write_text("---\nname: dataset-fetch\n---\n# x\n", encoding="utf-8")
    history = [{"round": 0, "problem_ids": ["DS_FETCH_NO_DATA"]}, {"round": 1, "problem_ids": []}]

    def brain(prompt, writes):
        schema.write_json(tmp_path, schema.SKILL_LESSON,
                          {"skill": "dataset-fetch", "title": "verify-urls-return-data",
                           "lesson": "curl -I every candidate URL; keep only 200 non-HTML."})
        return True

    learned = skill_upgrade.distill_and_persist(tmp_path, history, {"data_source": {"type": "dataset"}},
                                                brain=brain, bundle_dir=bundle)
    assert learned and learned["skill"] == "dataset-fetch"
    md = (bundle / "dataset-fetch" / "SKILL.md").read_text(encoding="utf-8")
    assert "verify-urls-return-data" in md and "self-upgrade" in md.lower() or "self-upgrade" in md
    # idempotent: a second identical distil does not duplicate
    assert skill_upgrade.distill_and_persist(tmp_path, history, {"data_source": {}}, brain=brain, bundle_dir=bundle) is None


def test_skill_upgrade_noop_on_clean_run(tmp_path):
    from dataset_lane import skill_upgrade
    called = {"brain": 0}

    def brain(prompt, writes):
        called["brain"] += 1
        return True

    out = skill_upgrade.distill_and_persist(tmp_path, [{"round": 0, "problem_ids": []}],
                                            {}, brain=brain, bundle_dir=tmp_path)
    assert out is None and called["brain"] == 0             # clean run: nothing to learn, no brain call


def test_lane_blocks_when_fetch_finds_no_data(tmp_path):
    def brain(prompt, writes):
        if schema.DOWNLOAD_PLAN in writes:
            schema.write_json(tmp_path, schema.DOWNLOAD_PLAN, [])   # agent resolved nothing
        return True

    def worker(prompt, writes):
        return True

    res = lane.run(tmp_path, {"data_source": {"type": "dataset", "url": "u"}},
                   brain=brain, worker=worker)
    assert res["ok"] is False and res["stage"] == "fetch"
    assert any(p["id"] in ("DS_FETCH_NO_MANIFEST", "DS_FETCH_NO_DATA", "DS_FETCH_UNAVAILABLE")
               for p in res["problems"])
