from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import http_app
from engine_v3.pipelines.paper import (
    BOUNDED_GOLDEN_OUTPUTS,
    DATA_OUTPUTS,
    FULL_PIPELINE_OUTPUTS,
    bounded_golden_pipeline,
    full_paper_pipeline,
)
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


def _full_fixture_runtime(golden_dir: Path):
    clean_draft = _clean_long_draft()

    def fixture_runner(command: list[str], cwd: Path, _timeout_s: int):
        prompt = command[-1]
        for rel in DATA_OUTPUTS:
            if rel in prompt:
                src = golden_dir / rel
                dst = cwd / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)
        if "phase3_positioning.md" in prompt:
            (cwd / "phase3_positioning.md").write_text("## Gap\nA-side gap.\n", encoding="utf-8")
        if "phase4_structure.md" in prompt:
            (cwd / "phase4_structure.md").write_text("## Structure\nIMRaD.\n", encoding="utf-8")
        if "claim_evidence_map.md" in prompt:
            (cwd / "claim_evidence_map.md").write_text(
                "| Claim | Evidence |\n"
                "|---|---|\n"
                "| k = 8; SMD -0.4327; I-squared 95.4 | real_results meta pooled |\n",
                encoding="utf-8",
            )
        if "paper_draft_v0.qmd" in prompt:
            for rel in [p for p in FULL_PIPELINE_OUTPUTS if p.startswith("sections/")]:
                path = cwd / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("section\n", encoding="utf-8")
            (cwd / "paper_draft_v0.qmd").write_text(clean_draft, encoding="utf-8")
        if "paper_springer.qmd" in prompt:
            (cwd / "paper_springer.qmd").write_text(clean_draft, encoding="utf-8")
        if "quality_review_round1.json" in prompt:
            (cwd / "quality_review_round1.json").write_text(
                '{"p0_count": 0, "delivery": "pass", "floor_100": 82.0}\n',
                encoding="utf-8",
            )
        if "paper_draft_v0.pdf" in prompt:
            (cwd / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
        return CliRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    return CodexCliRuntime(runner=fixture_runner)


def _clean_long_draft() -> str:
    sentence = (
        "The SMD pool included k = 8 effects. "
        "The pooled standardised mean difference was -0.4327, which indicates a reduction "
        "in depressive symptoms favouring exercise. "
        "Heterogeneity was considerable, with I-squared of 95.4, and this is consistent "
        "with a diverse study pool spanning different exercise modalities. "
        "The pooled estimate is directionally informative rather than clinically definitive."
    )
    return "\n\n".join([sentence for _ in range(90)])


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


def test_v3_status_includes_project_page_projection(tmp_path: Path, golden_dir: Path):
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
            v3_runtime_factory=lambda: _full_fixture_runtime(golden_dir),
            v3_phases_factory=full_paper_pipeline,
        )
    )
    created = tc.post(
        "/v3/jobs",
        json={
            "domain": "paper",
            "topic": "bounded golden",
            "research_question": "Does the intervention improve outcomes?",
            "contribution": "A reproducible rapid synthesis",
            "level": "master",
        },
        headers={"Authorization": "Bearer secret"},
    ).json()

    payload = tc.get(created["status_url"]).json()

    assert payload["research_plan"] == {
        "topic": "bounded golden",
        "research_question": "Does the intervention improve outcomes?",
        "contribution": "A reproducible rapid synthesis",
    }
    assert payload["tier"] == "master"
    assert "b_gap" in payload and "a_gap" in payload
    assert payload["summary"]["delivery"] == "pass"
    assert payload["artifacts"]["has_pdf"] is True
    assert payload["artifacts"]["pdf"].endswith("/artifact/paper_draft_v0.pdf")


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
