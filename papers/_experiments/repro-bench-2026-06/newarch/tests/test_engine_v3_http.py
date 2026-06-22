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
    ).status_code == 401


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


def test_v3_routes_absent_without_flag(tmp_path: Path):
    tc = TestClient(http_app.create_app(jobs_dir=tmp_path, start_worker=False))

    assert tc.post("/v3/jobs", json={}).status_code == 404
