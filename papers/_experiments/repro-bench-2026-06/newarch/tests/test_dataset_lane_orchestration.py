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
        "primary_model_id": "m1",
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


def _runner_factory(tmp_path, seen, fail_first=True):
    def fake_runner(rd, **kw):
        seen["rounds"] += 1
        rr = _good_real_results(Path(rd))
        if fail_first and seen["rounds"] == 1:
            rr["models"] = []                               # first run fails the schema gate
        schema.write_json(rd, schema.REAL_RESULTS, rr)
        out = Path(rd) / schema.REAL_RESULTS
        schema.write_json(rd, schema.EXECUTION_RECORD,
                          {"analysis_script_sha256": "S",
                           "manifest_sha256": (schema.read_json(rd, schema.MANIFEST) or {}).get("manifest_sha256"),
                           "real_results_sha256": "R", "real_results_mtime_unix": out.stat().st_mtime,
                           "returncode": 0, "started_at_unix": out.stat().st_mtime - 1,
                           "finished_at_unix": out.stat().st_mtime})
        return {}
    return fake_runner


def test_escalation_small_edit_worker_applies(tmp_path, monkeypatch):
    """Worker drafts non-empty code -> gate fails -> brain reviews 'SCOPE: small_edit' ->
    the cheap WORKER applies it. The brain does not take over a small fix."""
    seen = {"rounds": 0}

    def brain(prompt, writes):
        if schema.DOWNLOAD_PLAN in writes:
            schema.write_json(tmp_path, schema.DOWNLOAD_PLAN, [{"url": "u", "filename": "c.csv"}])
        elif schema.ANALYSIS_SPEC in writes:
            schema.write_json(tmp_path, schema.ANALYSIS_SPEC, {})
        elif schema.FIX_PRESCRIPTION in writes:
            (tmp_path / schema.FIX_PRESCRIPTION).write_text("SCOPE: small_edit\nadd the weights", encoding="utf-8")
        return True

    def worker(prompt, writes):
        if schema.ANALYSIS_CODE in writes:                  # worker drafts AND applies the small edit
            (tmp_path / schema.ANALYSIS_CODE).write_text("# a real draft with enough body to not be empty\n" * 3,
                                                          encoding="utf-8")
        return True

    monkeypatch.setattr(lane.fetch, "fetch", lambda rd, c, **k: _build_good_manifest(Path(rd)))
    monkeypatch.setattr(lane.runner, "run_analysis", _runner_factory(tmp_path, seen))
    res = lane.run(tmp_path, {"data_source": {"type": "dataset", "url": "u", "name": "F"}},
                   brain=brain, worker=worker, max_heal_rounds=2)
    assert res["ok"] is True
    assert any(h.get("applied_by") == "worker" for h in res["history"])   # worker applied the small fix
    assert res["escalated"] is False


def test_escalation_brain_takes_over_when_worker_empty(tmp_path, monkeypatch):
    """Worker drafts NOTHING -> brain reviews -> the BRAIN takes over and writes the code
    itself (the worker proved unable). applied_by=brain, escalated=True."""
    seen = {"rounds": 0}

    def brain(prompt, writes):
        if schema.DOWNLOAD_PLAN in writes:
            schema.write_json(tmp_path, schema.DOWNLOAD_PLAN, [{"url": "u", "filename": "c.csv"}])
        elif schema.ANALYSIS_SPEC in writes:
            schema.write_json(tmp_path, schema.ANALYSIS_SPEC, {})
        elif schema.FIX_PRESCRIPTION in writes:
            (tmp_path / schema.FIX_PRESCRIPTION).write_text("SCOPE: rewrite\nthe file is missing", encoding="utf-8")
        elif schema.ANALYSIS_CODE in writes:                # BRAIN takes over -> writes the code
            (tmp_path / schema.ANALYSIS_CODE).write_text("# brain-authored full analysis\n" * 4, encoding="utf-8")
        return True

    def worker(prompt, writes):
        return True                                          # worker writes NOTHING (its real failure mode)

    monkeypatch.setattr(lane.fetch, "fetch", lambda rd, c, **k: _build_good_manifest(Path(rd)))
    monkeypatch.setattr(lane.runner, "run_analysis", _runner_factory(tmp_path, seen))
    res = lane.run(tmp_path, {"data_source": {"type": "dataset", "url": "u", "name": "F"}},
                   brain=brain, worker=worker, max_heal_rounds=2)
    assert res["ok"] is True
    assert any(h.get("applied_by") == "brain" for h in res["history"]) and res["escalated"] is True


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
