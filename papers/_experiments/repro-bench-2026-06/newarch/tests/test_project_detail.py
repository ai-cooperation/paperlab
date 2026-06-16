"""Phase 9 (BSIDE_WEB_INTEGRATION_PLAN §5): the /v2/jobs/{id}/status projection carries
exactly the blocks the live page renders (research plan, b-gap, a-gap, tier) + terminal
status + PDF link, so engine_project_page.html (polled every 5s, no Hugo rebuild) can
render them. This pins the a-side data contract the Hugo template consumes.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import engine_routes
import http_app
from framework import Dossier

pytestmark = pytest.mark.integration


def _spawn(run_dir):
    d = Dossier.load(run_dir)
    c = d.data.get("contract", {})
    d.set("claims", {"b_gap": c.get("contribution") or c.get("research_question"),
                     "research_gaps": [{"description": "a-side gap"}]})
    d.pack_ext_set("run_result", {"floor_100": 70.7, "delivery": "blocked", "phases_done": []})
    d.update_status(run_status="done", phase="done")


def test_projection_feeds_the_four_page_blocks(tmp_path, load_fixture_json):
    app = http_app.create_app(jobs_dir=tmp_path, start_worker=False,
                              engine_v2=True, v2_spawn=_spawn)
    tc = TestClient(app)
    job_id = tc.post("/v2/jobs", json=load_fixture_json("contract_paper.json")).json()["job_id"]
    s = tc.get(f"/v2/jobs/{job_id}/status").json()

    assert s["research_plan"]["topic"] and s["research_plan"]["research_question"]
    assert "contribution" in s["research_plan"]                  # block 1: research plan
    assert s["b_gap"] and "a_gap" in s                          # blocks 2-3
    assert s["tier"] == "master" and "viability" in s          # block 4: tier + viability
    assert s["status"] and "blocked" in s                       # terminal status
    assert "pdf" in s["artifacts"] and "floor_100" in s["summary"]


def test_project_status_projection_shape_directly(tmp_path):
    dossier_data = {
        "run": {"job_id": "v2_x"},
        "status": {"phase": "done", "checkpoint": "review_heal", "blocked": True,
                   "run_status": "blocked"},
        "contract": {"topic": "T", "research_question": "Q", "contribution": "C", "level": "phd"},
        "claims": {"b_gap": "the grill gap", "research_gaps": [{"description": "a-side gap"}]},
        "viability": {"viable": True, "metric": {"max_poolable_k": 8}},
        "pack_ext": {"run_result": {"floor_100": 70.7, "delivery": "blocked"}},
    }
    proj = engine_routes.project_status(dossier_data, tmp_path)
    assert proj["status"] == "blocked" and proj["b_gap"] == "the grill gap"
    assert proj["a_gap"] == [{"description": "a-side gap"}]
    assert proj["tier"] == "phd" and proj["viability"]["viable"] is True
    assert proj["summary"]["floor_100"] == 70.7
    assert proj["artifacts"]["pdf"] is None                     # no pdf on disk in this tmp dir
