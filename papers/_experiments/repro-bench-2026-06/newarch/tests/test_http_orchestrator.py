"""Phase 7 + integration (BSIDE_WEB_INTEGRATION_PLAN §3a): POST /v2/jobs initialises
the dossier and DETACHES a worker (the real one runs pipeline.run_paper on ac-2012;
here a stub spawn stands in), returning a job_id fast; GET /v2/jobs/{id}/status returns
the enriched dossier projection. Idempotent replay + concurrency cap + old routes
untouched.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import http_app
from framework import Dossier

pytestmark = pytest.mark.integration


def _done_spawn(run_dir):
    """Stub worker: mark the job done + populate the projection fields run_paper would."""
    d = Dossier.load(run_dir)
    c = d.data.get("contract", {})
    d.set("claims", {"b_gap": c.get("contribution") or c.get("research_question"),
                     "research_gaps": [{"description": "a-side gap"}]})
    d.pack_ext_set("run_result", {"floor_100": 70.7, "delivery": "blocked",
                                  "phases_done": ["data", "gap", "review_heal"]})
    d.update_status(run_status="done", phase="done")


def _running_spawn(run_dir):
    Dossier.load(run_dir).update_status(run_status="running", phase="data")


@pytest.fixture
def client(tmp_path):
    app = http_app.create_app(jobs_dir=tmp_path, start_worker=False,
                              engine_v2=True, v2_spawn=_done_spawn)
    return TestClient(app), tmp_path


def test_v2_jobs_initialises_dossier_and_detaches_worker(client, load_fixture_json):
    tc, jobs_dir = client
    r = tc.post("/v2/jobs", json=load_fixture_json("contract_paper.json"))
    assert r.status_code == 202
    body = r.json()
    assert body["engine"] == "v2" and body["job_id"].startswith("v2_")
    assert body["status"] == "accepted" and body["status_url"].endswith("/status")
    dossier = json.loads((jobs_dir / body["job_id"] / "run" / "dossier.json").read_text())
    assert dossier["schema_version"] and dossier["run"]["mode"] == "paper"
    # the (stub) worker ran -> b_gap recorded
    assert dossier["claims"]["b_gap"]


def test_v2_status_enriched_projection(client, load_fixture_json):
    tc, _ = client
    job_id = tc.post("/v2/jobs", json=load_fixture_json("contract_paper.json")).json()["job_id"]
    s = tc.get(f"/v2/jobs/{job_id}/status").json()
    assert s["engine"] == "v2" and s["status"] == "done"          # terminal status (codex)
    assert set(s) >= {"phase", "tier", "research_plan", "b_gap", "a_gap",
                      "viability", "summary", "artifacts"}
    assert s["research_plan"]["topic"] and s["b_gap"] and s["tier"] == "master"
    assert s["summary"]["floor_100"] == 70.7 and s["summary"]["delivery"] == "blocked"
    assert "pdf" in s["artifacts"]                                # PDF link field present


def test_v2_idempotent_replay(client, load_fixture_json):
    tc, _ = client
    contract = load_fixture_json("contract_paper.json")
    first = tc.post("/v2/jobs", json=contract)
    second = tc.post("/v2/jobs", json=contract)                  # same contract -> same job_id
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.status_code == 200 and second.json()["status"] == "idempotent_replay"


def test_v2_concurrency_cap(tmp_path, load_fixture_json):
    # a running job occupies the single slot -> a different contract is refused 429
    app = http_app.create_app(jobs_dir=tmp_path, start_worker=False,
                              engine_v2=True, v2_spawn=_running_spawn, v2_max_concurrent=1)
    tc = TestClient(app)
    c1 = load_fixture_json("contract_paper.json")
    c2 = dict(c1); c2["topic"] = "a different topic"
    assert tc.post("/v2/jobs", json=c1).status_code == 202
    assert tc.post("/v2/jobs", json=c2).status_code == 429       # engine busy


def test_v2_status_404_for_unknown_job(client):
    tc, _ = client
    assert tc.get("/v2/jobs/v2_doesnotexist/status").status_code == 404


def test_old_pipeline_routes_untouched(client):
    tc, _ = client
    assert tc.get("/health").json()["status"] == "ok"
    assert tc.post("/jobs/dry-run", json={"not": "a contract"}).status_code in (200, 422)


def test_v2_routes_absent_without_flag(tmp_path):
    tc = TestClient(http_app.create_app(jobs_dir=tmp_path, start_worker=False))
    assert tc.post("/v2/jobs", json={}).status_code == 404
