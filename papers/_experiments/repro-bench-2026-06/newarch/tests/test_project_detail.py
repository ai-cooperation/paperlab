"""Phase 9 (ENGINE_BUILD_PLAN): live project page data contract (DESIGN §5.3).

The /v2/jobs/{id}/status projection must carry exactly the four blocks the live page
renders (research plan, b-gap, a-gap, tier decision) + phase progress, so the dynamic
page (engine_project_page.html, polled every 5s, no Hugo rebuild) can render them. The
Hugo template lives in the site repo; this pins the a-side data contract it consumes.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import engine_routes
import http_app
from framework import MockDispatcher

pytestmark = pytest.mark.integration


def test_projection_feeds_the_four_page_blocks(tmp_path, load_fixture_json):
    app = http_app.create_app(jobs_dir=tmp_path, start_worker=False,
                              engine_dispatcher=MockDispatcher())
    tc = TestClient(app)
    job_id = tc.post("/v2/jobs", json=load_fixture_json("contract_paper.json")).json()["job_id"]
    s = tc.get(f"/v2/jobs/{job_id}/status").json()

    # block 1: research plan
    assert s["research_plan"]["topic"] and s["research_plan"]["research_question"]
    assert "contribution" in s["research_plan"]
    # block 2: b-side gap   block 3: a-side gap   block 4: tier decision + viability
    assert "b_gap" in s and "a_gap" in s
    assert s["tier"] == "master" and "viability" in s
    # phase progress + block state
    assert s["phase"] and "blocked" in s and "delegations" in s


def test_project_status_projection_shape_directly(tmp_path):
    # the projection helper is pure -> testable without HTTP
    dossier_data = {
        "run": {"job_id": "v2_x"},
        "status": {"phase": "viable", "checkpoint": "intake", "blocked": False},
        "contract": {"topic": "T", "research_question": "Q", "contribution": "C", "level": "phd"},
        "claims": {"b_gap": "the grill gap", "research_gaps": [{"description": "a-side gap"}]},
        "viability": {"viable": True, "metric": {"max_poolable_k": 8}},
        "revision_loop": {"round": 1, "score": 82},
    }
    proj = engine_routes.project_status(dossier_data, tmp_path)
    assert proj["b_gap"] == "the grill gap"
    assert proj["a_gap"] == [{"description": "a-side gap"}]
    assert proj["tier"] == "phd" and proj["viability"]["viable"] is True
    assert proj["revision_loop"]["score"] == 82
