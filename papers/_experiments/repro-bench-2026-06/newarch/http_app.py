#!/usr/bin/env python3
"""FastAPI adapter for the validated paper job runner."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# the live progress page is served from this origin and fetches the read-only GET
# status/paper cross-origin — the browser needs Access-Control-Allow-Origin (CORS).
WEB_ORIGINS = ["https://paperlab.cooperation.tw"]

import capabilities
import job_runner
import router
import source_probe


DEFAULT_HTTP_JOBS_DIR = Path(os.environ.get("PAPER_JOBS_DIR", str(job_runner.DEFAULT_JOBS_DIR)))
IDEMPOTENCY_DIRNAME = "_idempotency"


def payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def idempotency_path(jobs_dir: Path, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return jobs_dir.expanduser().resolve() / IDEMPOTENCY_DIRNAME / f"{digest}.json"


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def contribution_from_b_contract(contract: dict[str, Any]) -> str | None:
    contribution = contract.get("contribution")
    if isinstance(contribution, str) and contribution.strip():
        return contribution.strip()
    contribution_type = str(contract.get("contribution_type") or "").strip()
    innovation_point = str(contract.get("innovation_point") or "").strip()
    if contribution_type and innovation_point:
        return f"{contribution_type}: {innovation_point}"
    if contribution_type:
        return contribution_type
    return None


def normalize_data_source(data_source: Any) -> Any:
    if not isinstance(data_source, dict):
        return data_source
    probe_required = data_source.get("probe_required")
    return {
        **data_source,
        "probe_required": probe_required if isinstance(probe_required, bool) else True,
    }


def normalize_contract(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the b-side grill contract shape into a's validated schema."""
    contribution = contribution_from_b_contract(payload)
    normalized = {
        **payload,
        "data_source": normalize_data_source(payload.get("data_source")),
    }
    if contribution is not None:
        normalized = {**normalized, "contribution": contribution}
    router.validate_contract(normalized)
    return normalized


def route_payload(payload: dict[str, Any]) -> dict[str, Any]:
    contract = normalize_contract(payload)
    decision = router.route_contract(contract)
    return {
        "valid": True,
        "research_contract": contract,
        "routing_decision": decision,
        "level": decision.get("level"),
        "content_threshold": decision.get("content_threshold"),
        "review_depth": decision.get("review_depth"),
    }


async def request_json_object(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="request body must be a JSON object")
    return payload


def submit_contract(contract: dict[str, Any], jobs_dir: Path, start_worker: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        contract_path = Path(tmp) / "research_contract.json"
        write_json(contract_path, contract)
        return job_runner.submit(contract_path, jobs_dir, start_worker=start_worker)


def public_status(state: dict[str, Any]) -> dict[str, Any]:
    decision = state.get("routing_decision") if isinstance(state.get("routing_decision"), dict) else {}
    return {
        "job_id": state.get("job_id"),
        "status": state.get("status"),
        "level": state.get("level") or decision.get("level"),
        "tier": state.get("tier"),
        "content_threshold": decision.get("content_threshold"),
        "review_depth": decision.get("review_depth"),
        "run_dir": state.get("run_dir"),
        "worker_pid": state.get("worker_pid"),
        "repo_url": state.get("repo_url"),
        "repo_sync": state.get("repo_sync"),
        "notification": state.get("notification"),
        "updated_at": state.get("updated_at"),
        "history": state.get("history", []),
    }


def public_result(output: dict[str, Any]) -> dict[str, Any]:
    return {
        **output,
        "pdf": output.get("pdf_path"),
    }


def paper_path_for_job(job_id: str, jobs_dir: Path) -> Path:
    state = job_runner.status(job_id, jobs_dir)
    run_dir = state.get("run_dir")
    if not isinstance(run_dir, str) or not run_dir.strip():
        raise FileNotFoundError(f"paper PDF is not ready for job_id: {job_id}")
    pdf = Path(run_dir).expanduser().resolve() / "paper_draft_v0.pdf"
    if not pdf.is_file():
        raise FileNotFoundError(f"paper PDF is not ready for job_id: {job_id}")
    return pdf


def create_app(jobs_dir: Path = DEFAULT_HTTP_JOBS_DIR, start_worker: bool = True,
               engine_v2: bool = False, v2_spawn: Any = None,
               v2_max_concurrent: int = 1,
               engine_v3: bool = False,
               v3_auth_token: str | None = None,
               v3_max_live_jobs: int | None = None,
               v3_runtime_factory: Any = None,
               v3_phases_factory: Any = None) -> FastAPI:
    app = FastAPI(title="Paper Job Service", version=job_runner.RUNNER_VERSION)
    # Let the public live progress page (paperlab.cooperation.tw) fetch the read-only
    # GET status/paper across origin. Scoped to that origin + GET only — the b-side
    # Worker POSTs server-to-server (token), so POST routes stay non-CORS.
    app.add_middleware(CORSMiddleware, allow_origins=WEB_ORIGINS,
                       allow_methods=["GET", "OPTIONS"], allow_headers=["*"])
    resolved_jobs_dir = jobs_dir.expanduser().resolve()

    # Engine-v2 routes mount ALONGSIDE the old pipeline for A/B (P7: never churn prod
    # around an unproven orchestrator). POST /v2/jobs detaches a v2_worker subprocess
    # running the full pipeline; the old paper_driver pipeline on /jobs is untouched.
    # v2_spawn is injectable so tests stub the heavy worker.
    if engine_v2:
        import engine_routes
        kw: dict[str, Any] = {"max_concurrent": v2_max_concurrent}
        if v2_spawn is not None:
            kw["spawn"] = v2_spawn
        engine_routes.register(app, resolved_jobs_dir, **kw)

    if engine_v3:
        from engine_v3 import routes as engine_v3_routes
        engine_v3_routes.register(
            app,
            resolved_jobs_dir,
            auth_token=v3_auth_token or os.environ.get("PAPER_ENGINE_V3_TOKEN"),
            max_live_jobs=v3_max_live_jobs
            if v3_max_live_jobs is not None
            else int(os.environ.get("PAPER_ENGINE_V3_MAX_LIVE_JOBS", "1")),
            runtime_factory=v3_runtime_factory,
            phases_factory=v3_phases_factory,
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "jobs_dir": str(resolved_jobs_dir), "runner_version": job_runner.RUNNER_VERSION}

    @app.get("/capabilities")
    def capabilities_endpoint() -> dict[str, Any]:
        # b negotiates against this: submit a v2 contract only when schema_hash +
        # contract_version + recipe_id match what a advertises here.
        return capabilities.capabilities()

    @app.get("/schema/contract_v2.schema.json")
    def contract_schema() -> Response:
        return Response(content=capabilities.schema_text(), media_type="application/json")

    @app.post("/jobs/dry-run")
    async def dry_run(request: Request) -> dict[str, Any]:
        payload = await request_json_object(request)
        try:
            return route_payload(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/jobs", status_code=202)
    async def create_job(
        request: Request,
        response: Response,
        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        if not idempotency_key or not idempotency_key.strip():
            raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
        payload = await request_json_object(request)
        try:
            contract = normalize_contract(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # v2 executability gate: a real-experiment contract must resolve against an a-side
        # recipe BEFORE the job is accepted (schema validity != executability).
        if contract.get("contract_version") == 2:
            v = capabilities.validate_experiment_contract(contract)
            if not v["ok"]:
                raise HTTPException(status_code=422,
                                    detail={"error": "experiment not executable", "errors": v["errors"]})

        key_path = idempotency_path(resolved_jobs_dir, idempotency_key.strip())
        existing = read_json(key_path)
        body_hash = payload_hash(contract)
        if existing is not None:
            if existing.get("request_hash") != body_hash:
                raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different contract")
            response.status_code = 200
            return {
                "job_id": existing.get("job_id"),
                "status": existing.get("status", "submitted"),
                "idempotent_replay": True,
            }

        try:
            submitted = submit_contract(contract, resolved_jobs_dir, start_worker=start_worker)
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        record = {
            "key_hash": key_path.stem,
            "request_hash": body_hash,
            "job_id": submitted["job_id"],
            "status": submitted["status"],
            "state_path": submitted["state_path"],
            "created_at": job_runner.now_iso(),
        }
        write_json(key_path, record)
        return {**submitted, "idempotent_replay": False}

    @app.post("/jobs/probe-data-source")
    async def probe_data_source(request: Request) -> dict[str, Any]:
        # Grill Step-4 confirmation (PAPER_MCP_GRILL_DESIGN.md): generalised probe
        # of ANY public source (HUPD / dataset|api URL / literature corpus). Takes
        # the raw partial grill payload (no full-contract normalization) and only
        # CONFIRMS reachability — it does not collect data or run a job.
        payload = await request_json_object(request)
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "probe"
            run_dir.mkdir(parents=True, exist_ok=True)
            return source_probe.probe(payload, run_dir)

    @app.get("/jobs/{job_id}/status")
    def get_status(job_id: str) -> dict[str, Any]:
        try:
            return public_status(job_runner.status(job_id, resolved_jobs_dir))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/jobs/{job_id}/result")
    def get_result(job_id: str) -> dict[str, Any]:
        try:
            return public_result(job_runner.result(job_id, resolved_jobs_dir))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/jobs/{job_id}/paper")
    def get_paper(job_id: str) -> FileResponse:
        try:
            pdf = paper_path_for_job(job_id, resolved_jobs_dir)
            return FileResponse(pdf, media_type="application/pdf", filename=f"{job_id}.pdf")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return app


def app_from_env() -> FastAPI:
    jobs_dir = Path(os.environ.get("PAPER_JOBS_DIR", str(job_runner.DEFAULT_JOBS_DIR)))
    return create_app(
        jobs_dir=jobs_dir,
        engine_v2=os.environ.get("PAPER_ENGINE_V2") == "1",
        engine_v3=os.environ.get("PAPER_ENGINE_V3") == "1",
    )


# Engine v2/v3 routes mount only when the corresponding env flag is set (A/B opt-in).
app = app_from_env()
