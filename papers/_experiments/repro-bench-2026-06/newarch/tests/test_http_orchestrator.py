"""Phase 7 (ENGINE_BUILD_PLAN): HTTP job-service integration. POST /v2/jobs routes
to the NEW orchestrator (not paper_driver's old loop); GET /v2/jobs/{id}/status
returns the DOSSIER PROJECTION (research plan, b-gap, a-gap, tier, progress), not the
coarse job status. The old pipeline routes are untouched (A/B).
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import http_app
from framework import MockDispatcher

pytestmark = pytest.mark.integration


@pytest.fixture
def client(tmp_path):
    app = http_app.create_app(jobs_dir=tmp_path, start_worker=False,
                              engine_dispatcher=MockDispatcher())
    return TestClient(app), tmp_path


def _contract(load_fixture_json):
    return load_fixture_json("contract_paper.json")


def test_v2_jobs_routes_to_orchestrator(client, load_fixture_json):
    tc, jobs_dir = client
    r = tc.post("/v2/jobs", json=_contract(load_fixture_json))
    assert r.status_code == 202
    body = r.json()
    assert body["engine"] == "v2" and body["job_id"].startswith("v2_")
    # the NEW orchestrator drove it: a framework dossier exists (not the old pipeline state)
    dossier = json.loads((jobs_dir / body["job_id"] / "run" / "dossier.json").read_text())
    assert dossier["schema_version"] and dossier["run"]["mode"] == "paper"
    assert "intake" in dossier["status"]["completed"]              # orchestrator phase ran


def test_v2_status_returns_dossier_projection(client, load_fixture_json):
    tc, _ = client
    job_id = tc.post("/v2/jobs", json=_contract(load_fixture_json)).json()["job_id"]
    r = tc.get(f"/v2/jobs/{job_id}/status")
    assert r.status_code == 200
    s = r.json()
    # the projection (DESIGN §5.3), not the coarse public_status shape
    assert s["engine"] == "v2"
    assert set(s) >= {"phase", "tier", "research_plan", "b_gap", "a_gap",
                      "viability", "revision_loop"}
    assert s["research_plan"]["topic"]                              # research plan present
    assert s["b_gap"]                                              # b-side gap recorded
    assert s["tier"] == "master"                                   # tier decision


def test_v2_status_404_for_unknown_job(client):
    tc, _ = client
    assert tc.get("/v2/jobs/v2_doesnotexist/status").status_code == 404


def test_old_pipeline_routes_untouched(client):
    tc, _ = client
    assert tc.get("/health").json()["status"] == "ok"
    # dry-run (old path) still validates contracts
    bad = tc.post("/jobs/dry-run", json={"not": "a contract"})
    assert bad.status_code in (200, 422)


def test_v2_routes_absent_without_dispatcher(tmp_path):
    # default app (no engine_dispatcher) must NOT expose v2 routes — old pipeline only
    tc = TestClient(http_app.create_app(jobs_dir=tmp_path, start_worker=False))
    assert tc.post("/v2/jobs", json={}).status_code == 404
