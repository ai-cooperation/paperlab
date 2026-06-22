from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response

from engine_v3.core import DossierStore
from engine_v3.core.orchestrator import EngineV3Orchestrator
from engine_v3.packs.paper import PaperPack
from engine_v3.pipelines.paper import bounded_golden_pipeline
from engine_v3.runtimes.codex_cli import CodexCliRuntime


RuntimeFactory = Callable[[], object]
PhasesFactory = Callable[[], list]
LOCK_DIRNAME = "_locks_v3"
IDEMPOTENCY_DIRNAME = "_idempotency_v3"


def register(
    app: FastAPI,
    jobs_dir: Path,
    *,
    auth_token: Optional[str],
    runtime_factory: Optional[RuntimeFactory] = None,
    phases_factory: Optional[PhasesFactory] = None,
) -> None:
    jobs_dir = jobs_dir.expanduser().resolve()

    def _run_dir(job_id: str) -> Path:
        return jobs_dir / job_id / "run"

    def _lock_path(job_id: str) -> Path:
        return jobs_dir / LOCK_DIRNAME / (job_id + ".lock")

    def _idempotency_path(key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return jobs_dir / IDEMPOTENCY_DIRNAME / (digest + ".json")

    async def _json(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="body must be a JSON object")
        return payload

    @app.get("/v3/health")
    def v3_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "engine": "v3",
            "jobs_dir": str(jobs_dir),
        }

    @app.get("/v3/capabilities")
    def v3_capabilities() -> dict[str, Any]:
        pack = PaperPack()
        return {
            "engine": "v3",
            "packs": [pack.name],
            "default_pack": pack.name,
            "runtimes": ["codex-cli", "hermes-codex", "mock"],
            "routes": [
                "GET /v3/health",
                "GET /v3/capabilities",
                "GET /v3/schema/{pack}/contract_v3.schema.json",
                "POST /v3/jobs",
                "GET /v3/jobs/{job_id}/status",
            ],
        }

    @app.get("/v3/schema/{pack}/contract_v3.schema.json")
    def v3_contract_schema(pack: str) -> dict[str, Any]:
        if pack != "paper":
            raise HTTPException(status_code=404, detail="unknown v3 pack")
        return dict(PaperPack().contract_schema())

    @app.post("/v3/jobs", status_code=202)
    async def create_v3_job(
        request: Request,
        response: Response,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        _require_post_auth(authorization, auth_token)
        contract = await _json(request)
        request_hash = _request_hash(contract)
        key_path = _idempotency_path(idempotency_key.strip()) if idempotency_key and idempotency_key.strip() else None
        existing_key = _read_json(key_path) if key_path is not None else None
        if existing_key is not None:
            if existing_key.get("request_hash") != request_hash:
                raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different contract")
            response.status_code = 200
            return {
                "engine": "v3",
                "job_id": existing_key.get("job_id"),
                "status": existing_key.get("status", "done"),
                "status_url": existing_key.get("status_url"),
                "idempotent_replay": True,
            }

        job_id = _job_id(contract)
        run_dir = _run_dir(job_id)
        status_url = f"/v3/jobs/{job_id}/status"

        store = DossierStore(run_dir)
        if store.exists():
            response.status_code = 200
            dossier = store.load()
            return {
                "engine": "v3",
                "job_id": job_id,
                "status": _status(dossier.phases),
                "status_url": status_url,
                "idempotent_replay": True,
            }

        lock_fd = _claim_lock(_lock_path(job_id))
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            (run_dir / "research_contract.input.json").write_text(
                json.dumps(contract, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            pack = PaperPack()
            runtime = runtime_factory() if runtime_factory is not None else CodexCliRuntime()
            phases = phases_factory() if phases_factory is not None else bounded_golden_pipeline()
            dossier = EngineV3Orchestrator(
                runtime=runtime,
                domain_pack=pack,
                phases=phases,
                dossier_store=store,
            ).run(job_id=job_id, resume=False)
        finally:
            os.close(lock_fd)

        status = _status(dossier.phases)
        if key_path is not None:
            _write_json(
                key_path,
                {
                    "request_hash": request_hash,
                    "job_id": job_id,
                    "status": status,
                    "status_url": status_url,
                },
            )
        return {
            "engine": "v3",
            "job_id": job_id,
            "status": status,
            "status_url": status_url,
            "idempotent_replay": False,
        }

    @app.get("/v3/jobs/{job_id}/status")
    def v3_status(job_id: str) -> dict[str, Any]:
        store = DossierStore(_run_dir(job_id))
        if not store.exists():
            raise HTTPException(status_code=404, detail="job not found")
        dossier = store.load()
        return {
            "engine": "v3",
            "job_id": dossier.job_id,
            "status": _status(dossier.phases),
            "domain": dossier.domain,
            "phases": dict(dossier.phases),
            "delegations": list(dossier.delegations),
            "gates": list(dossier.gate_reports),
            "artifacts": {
                name: {"path": ref.path, "sha256": ref.sha256}
                for name, ref in dossier.artifacts.items()
            },
        }


def _require_post_auth(authorization: Optional[str], auth_token: Optional[str]) -> None:
    if not auth_token:
        raise HTTPException(status_code=503, detail="v3 auth token is not configured")
    if not authorization:
        raise HTTPException(status_code=401, detail="missing bearer token")
    expected = "Bearer %s" % auth_token
    if not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=403, detail="invalid bearer token")


def _job_id(contract: dict[str, Any]) -> str:
    return "v3_" + _request_hash(contract)[:12]


def _request_hash(contract: dict[str, Any]) -> str:
    blob = json.dumps(contract, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _status(phases: dict[str, str]) -> str:
    if not phases:
        return "accepted"
    if any(status == "error" for status in phases.values()):
        return "failed"
    if any(status == "blocked" for status in phases.values()):
        return "blocked"
    return "done"


def _claim_lock(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail="job creation is already in progress") from exc


def _read_json(path: Optional[Path]) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
