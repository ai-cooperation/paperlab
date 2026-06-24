from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import http_app
from engine_v3.pipelines.paper import BOUNDED_GOLDEN_OUTPUTS, bounded_golden_pipeline
from engine_v3.runtimes.codex_cli import CliRunResult, CodexCliRuntime

pytestmark = pytest.mark.integration


def _fixture_runtime(golden_dir: Path):
    def fixture_runner(command: list[str], cwd: Path, _timeout_s: int):
        prompt = command[-1]
        for rel in BOUNDED_GOLDEN_OUTPUTS:
            if rel not in prompt:
                continue
            src = golden_dir / rel
            dst = cwd / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
        return CliRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    return CodexCliRuntime(runner=fixture_runner)


def test_v3_jobs_require_bearer_token(tmp_path: Path):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
        )
    )

    assert tc.post("/v3/jobs", json={"topic": "x"}).status_code == 401
    assert tc.post(
        "/v3/jobs",
        json={"topic": "x"},
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 403


def test_v3_viability_probe_requires_bearer_token(tmp_path: Path):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
        )
    )

    assert tc.post("/v3/jobs/viability-probe", json={}).status_code == 401


def test_v3_job_runs_bounded_golden_and_status(tmp_path: Path, golden_dir: Path):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
            v3_runtime_factory=lambda: _fixture_runtime(golden_dir),
            v3_phases_factory=bounded_golden_pipeline,
        )
    )

    created = tc.post(
        "/v3/jobs",
        json={"domain": "paper", "topic": "bounded golden"},
        headers={"Authorization": "Bearer secret"},
    )

    assert created.status_code == 202
    body = created.json()
    assert body["engine"] == "v3"
    assert body["status"] == "done"
    assert body["job_id"].startswith("v3_")
    status = tc.get(body["status_url"])
    assert status.status_code == 200
    payload = status.json()
    assert payload["engine"] == "v3"
    assert payload["status"] == "done"
    assert payload["phases"] == {"data": "done", "render_gates": "done"}
    assert all(report["blocked"] is False for report in payload["gates"])


def test_v3_artifact_route_serves_only_indexed_artifacts(tmp_path: Path, golden_dir: Path):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
            v3_runtime_factory=lambda: _fixture_runtime(golden_dir),
            v3_phases_factory=bounded_golden_pipeline,
        )
    )
    created = tc.post(
        "/v3/jobs",
        json={"domain": "paper", "topic": "artifact route"},
        headers={"Authorization": "Bearer secret"},
    ).json()
    job_id = created["job_id"]

    bib = tc.get(f"/v3/jobs/{job_id}/artifact/references.bib")
    nested = tc.get(f"/v3/jobs/{job_id}/artifact/real_experiments/real_results.json")
    missing = tc.get(f"/v3/jobs/{job_id}/artifact/not-indexed.txt")
    traversal = tc.get(f"/v3/jobs/{job_id}/artifact/../../research_contract.input.json")

    assert bib.status_code == 200
    assert "@article" in bib.text or "@misc" in bib.text
    assert nested.status_code == 200
    assert nested.json()["meta"]["pooled"]
    assert missing.status_code == 404
    assert traversal.status_code == 404


def test_v3_submit_idempotent_replay_same_hash(tmp_path: Path, golden_dir: Path):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
            v3_runtime_factory=lambda: _fixture_runtime(golden_dir),
            v3_phases_factory=bounded_golden_pipeline,
        )
    )
    headers = {"Authorization": "Bearer secret", "Idempotency-Key": "same"}
    contract = {"domain": "paper", "topic": "bounded golden"}

    first = tc.post("/v3/jobs", json=contract, headers=headers)
    second = tc.post("/v3/jobs", json=contract, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.json()["idempotent_replay"] is True


def test_v3_submit_conflict_different_hash(tmp_path: Path, golden_dir: Path):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
            v3_runtime_factory=lambda: _fixture_runtime(golden_dir),
            v3_phases_factory=bounded_golden_pipeline,
        )
    )
    headers = {"Authorization": "Bearer secret", "Idempotency-Key": "same"}

    first = tc.post("/v3/jobs", json={"domain": "paper", "topic": "a"}, headers=headers)
    second = tc.post("/v3/jobs", json={"domain": "paper", "topic": "b"}, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 409


def test_v3_job_creation_lock_blocks_unclaimed_duplicate(tmp_path: Path):
    contract = {"domain": "paper", "topic": "locked"}
    import engine_v3.routes as routes

    job_id = routes._job_id(contract)
    lock_dir = tmp_path / "_locks_v3"
    lock_dir.mkdir()
    (lock_dir / (job_id + ".lock")).write_text("busy", encoding="utf-8")
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
        )
    )

    response = tc.post(
        "/v3/jobs",
        json=contract,
        headers={"Authorization": "Bearer secret"},
    )

    assert response.status_code == 409


def test_v3_worker_crash_sets_failed_state(tmp_path: Path):
    class CrashingRuntime:
        name = "crashing"

        def prepare(self, _context):
            raise RuntimeError("runtime exploded")

    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
            v3_runtime_factory=lambda: CrashingRuntime(),
            v3_phases_factory=bounded_golden_pipeline,
        )
    )

    created = tc.post(
        "/v3/jobs",
        json={"domain": "paper", "topic": "crash"},
        headers={"Authorization": "Bearer secret"},
    )

    assert created.status_code == 202
    assert created.json()["status"] == "failed"
    status = tc.get(created.json()["status_url"])
    assert status.status_code == 200
    assert status.json()["status"] == "failed"
    assert status.json()["phases"] == {"system": "error"}
    assert status.json()["error"]["type"] == "RuntimeError"


def test_v3_routes_absent_without_flag(tmp_path: Path):
    tc = TestClient(http_app.create_app(jobs_dir=tmp_path, start_worker=False))

    assert tc.post("/v3/jobs", json={}).status_code == 404


def test_v3_health_capabilities_and_schema(tmp_path: Path):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
        )
    )

    health = tc.get("/v3/health")
    capabilities = tc.get("/v3/capabilities")
    schema = tc.get("/v3/schema/paper/contract_v3.schema.json")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert capabilities.status_code == 200
    assert capabilities.json()["engine"] == "v3"
    assert "paper" in capabilities.json()["packs"]
    assert capabilities.json()["default_pipeline"] == "full_paper_pipeline"
    assert schema.status_code == 200
    assert schema.json()["type"] == "object"


def test_v3_viability_probe_uses_paper_pack(tmp_path: Path, load_fixture_json):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
        )
    )
    response = tc.post(
        "/v3/jobs/viability-probe",
        json={
            "contract": load_fixture_json("contract_paper.json"),
            "sources": {"corpus": load_fixture_json("corpus_exercise.json")},
        },
        headers={"Authorization": "Bearer secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "v3"
    assert body["domain"] == "paper"
    assert body["viable"] is True
    assert body["metric"]["max_poolable_k"] == 8
    assert body["contract_hash"]
