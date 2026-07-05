from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import http_app
from engine_v3.core import DossierStore
from engine_v3.core.orchestrator import _maybe_require_vip_delivery_review

pytestmark = pytest.mark.unit


def _make_done_dossier(run_dir: Path, *, tier: str | None = "vip"):
    run_dir.mkdir(parents=True, exist_ok=True)
    contract = {"topic": "t", "research_question": "q"}
    if tier:
        contract["level"] = tier
    (run_dir / "research_contract.json").write_text(json.dumps(contract), encoding="utf-8")
    store = DossierStore(run_dir)
    dossier = store.create(job_id="v3_vip_test", domain="paper")
    for phase in ("data", "write", "review_heal", "format_repair"):
        dossier.mark_phase(phase, "done")
    store.save(dossier)
    return store, dossier


def test_vip_job_with_all_phases_done_requires_human_review(tmp_path: Path):
    run_dir = tmp_path / "run"
    store, dossier = _make_done_dossier(run_dir, tier="vip")

    changed = _maybe_require_vip_delivery_review(dossier, run_dir)

    assert changed is True
    checkpoint = dossier.evidence["human_checkpoint"]
    assert checkpoint["status"] == "human_review_required"
    assert checkpoint["phase"] == "delivery"


def test_non_vip_job_does_not_get_delivery_checkpoint(tmp_path: Path):
    run_dir = tmp_path / "run"
    store, dossier = _make_done_dossier(run_dir, tier="standard")

    assert _maybe_require_vip_delivery_review(dossier, run_dir) is False
    assert "human_checkpoint" not in dossier.evidence


def test_blocked_job_does_not_get_delivery_checkpoint(tmp_path: Path):
    run_dir = tmp_path / "run"
    store, dossier = _make_done_dossier(run_dir, tier="vip")
    dossier.mark_phase("review_heal", "blocked")

    assert _maybe_require_vip_delivery_review(dossier, run_dir) is False


def test_recorded_approval_clears_the_checkpoint(tmp_path: Path):
    run_dir = tmp_path / "run"
    store, dossier = _make_done_dossier(run_dir, tier="vip")
    (run_dir / "human_review_approval.json").write_text(
        json.dumps({"approved": True, "approved_by": "alan", "approved_at": "2026-07-02T12:00:00Z"}),
        encoding="utf-8",
    )

    changed = _maybe_require_vip_delivery_review(dossier, run_dir)

    assert changed is True
    assert dossier.evidence["human_checkpoint"]["status"] == "approved"
    assert dossier.evidence["human_checkpoint"]["approved_by"] == "alan"


def test_status_endpoint_surfaces_human_review_and_approval_flow(tmp_path: Path):
    jobs_dir = tmp_path / "jobs"
    run_dir = jobs_dir / "v3_vip_test" / "run"
    store, dossier = _make_done_dossier(run_dir, tier="vip")
    _maybe_require_vip_delivery_review(dossier, run_dir)
    store.save(dossier)

    tc = TestClient(
        http_app.create_app(
            jobs_dir=jobs_dir,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
        )
    )

    status = tc.get("/v3/jobs/v3_vip_test/status").json()
    assert status["status"] == "human_review_required"
    assert status["human_checkpoint"]["phase"] == "delivery"

    denied = tc.post("/v3/jobs/v3_vip_test/human-review", json={"decision": "approve"})
    assert denied.status_code == 401

    approved = tc.post(
        "/v3/jobs/v3_vip_test/human-review",
        json={"decision": "approve", "reviewer": "alan"},
        headers={"Authorization": "Bearer secret"},
    )
    assert approved.status_code == 200
    assert approved.json()["human_checkpoint"]["status"] == "approved"
    assert json.loads((run_dir / "human_review_approval.json").read_text(encoding="utf-8"))["approved"] is True

    status_after = tc.get("/v3/jobs/v3_vip_test/status").json()
    assert status_after["status"] == "done"


def test_vip_in_tier_field_triggers_checkpoint_even_when_level_is_journal(tmp_path: Path):
    """run5 shipped level=journal, tier=vip and the checkpoint silently
    skipped because only the first non-empty field was inspected."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "research_contract.json").write_text(
        json.dumps({"topic": "t", "level": "journal", "tier": "vip"}), encoding="utf-8"
    )
    store = DossierStore(run_dir)
    dossier = store.create(job_id="v3_vip_test", domain="paper")
    for phase in ("data", "review_heal", "format_repair"):
        dossier.mark_phase(phase, "done")

    assert _maybe_require_vip_delivery_review(dossier, run_dir) is True
    assert dossier.evidence["human_checkpoint"]["status"] == "human_review_required"


def test_stale_phase_checkpoint_cleared_when_all_phases_done(tmp_path: Path):
    run_dir = tmp_path / "run"
    store, dossier = _make_done_dossier(run_dir, tier="standard")
    dossier.evidence["human_checkpoint"] = {
        "status": "human_decision_required",
        "phase": "data",
        "reason": "superseded: data later passed",
    }

    assert _maybe_require_vip_delivery_review(dossier, run_dir) is False
    assert "human_checkpoint" not in dossier.evidence


def test_vip_delivery_checkpoint_replaces_stale_phase_checkpoint(tmp_path: Path):
    run_dir = tmp_path / "run"
    store, dossier = _make_done_dossier(run_dir, tier="vip")
    dossier.evidence["human_checkpoint"] = {
        "status": "human_decision_required",
        "phase": "data",
        "reason": "superseded: data later passed",
    }

    assert _maybe_require_vip_delivery_review(dossier, run_dir) is True
    checkpoint = dossier.evidence["human_checkpoint"]
    assert checkpoint["status"] == "human_review_required"
    assert checkpoint["phase"] == "delivery"


def test_stale_checkpoint_clearing_is_persisted_for_non_vip_runs(tmp_path: Path):
    """Job v3_11c16e4b8735 finished done_pass with a superseded data-phase
    human_decision_required checkpoint still in the SAVED dossier: run()
    only saved after the VIP check when a delivery checkpoint was ADDED
    (returned True); the non-VIP path cleared the stale checkpoint in
    memory and never persisted the clearing, so the status page kept
    telling a done job it needed a human decision."""
    from engine_v3.core import DossierStore
    from engine_v3.core.orchestrator import EngineV3Orchestrator, PhaseSpec
    from engine_v3.runtimes.mock import MockRuntime

    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "research_contract.json").write_text(
        json.dumps({"topic": "t", "research_question": "q", "level": "standard"}),
        encoding="utf-8",
    )
    store = DossierStore(run_dir)
    dossier = store.create(job_id="job-1", domain="paper")
    dossier.evidence["human_checkpoint"] = {
        "status": "human_decision_required",
        "phase": "data",
        "reason": "superseded: data later passed",
    }
    store.save(dossier)

    orchestrator = EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=object(),
        phases=[PhaseSpec(id="phase-0", handler=lambda _task, _context: {})],
        dossier_store=store,
    )
    orchestrator.run(job_id="job-1", resume=True)

    reloaded = store.load()
    assert "human_checkpoint" not in reloaded.evidence
