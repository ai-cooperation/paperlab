from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse

from engine_v3.core import DossierStore
from engine_v3.core.dossier import hash_file
from engine_v3.core.orchestrator import EngineV3Orchestrator
from engine_v3.packs.paper import PaperPack
from engine_v3.pipelines.paper import full_paper_pipeline
from engine_v3.runtime_config import runtime_from_env


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
            "default_pipeline": "full_paper_pipeline",
            "runtimes": ["codex-cli", "hermes-codex", "mock"],
            "routes": [
                "GET /v3/health",
                "GET /v3/capabilities",
                "GET /v3/schema/{pack}/contract_v3.schema.json",
                "POST /v3/jobs",
                "GET /v3/jobs/{job_id}/status",
                "GET /v3/jobs/{job_id}/artifact/{artifact_id}",
            ],
        }

    @app.get("/v3/schema/{pack}/contract_v3.schema.json")
    def v3_contract_schema(pack: str) -> dict[str, Any]:
        if pack != "paper":
            raise HTTPException(status_code=404, detail="unknown v3 pack")
        return dict(PaperPack().contract_schema())

    @app.post("/v3/jobs/viability-probe")
    async def v3_viability_probe(
        request: Request,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        _require_post_auth(authorization, auth_token)
        payload = await _json(request)
        contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else payload
        sources = payload.get("sources") if isinstance(payload.get("sources"), dict) else {}
        pack = PaperPack()
        verdict = pack.viability_probe(contract, sources)
        body = _jsonable(verdict)
        return {
            "engine": "v3",
            "domain": pack.name,
            **body,
        }

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
            runtime = runtime_factory() if runtime_factory is not None else runtime_from_env()
            phases = phases_factory() if phases_factory is not None else full_paper_pipeline()
            try:
                dossier = EngineV3Orchestrator(
                    runtime=runtime,
                    domain_pack=pack,
                    phases=phases,
                    dossier_store=store,
                ).run(job_id=job_id, resume=False)
            except Exception as exc:  # noqa: BLE001 - failed jobs must be inspectable.
                dossier = _failed_dossier(store, job_id, pack.name, exc)
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
        run_dir = _run_dir(job_id)
        store = DossierStore(run_dir)
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
            "error": dossier.evidence.get("error"),
            **_project_status(dossier, run_dir),
        }

    @app.get("/v3/jobs/{job_id}/artifact/{artifact_id:path}")
    def v3_artifact(job_id: str, artifact_id: str) -> FileResponse:
        run_dir = _run_dir(job_id)
        store = DossierStore(run_dir)
        if not store.exists():
            raise HTTPException(status_code=404, detail="job not found")
        dossier = store.load()
        ref = dossier.artifacts.get(artifact_id)
        if ref is None:
            raise HTTPException(status_code=404, detail="artifact not found")

        path = _indexed_artifact_path(run_dir, ref.path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="artifact file not found")
        if hash_file(path) != ref.sha256:
            raise HTTPException(status_code=409, detail="artifact hash mismatch")
        return FileResponse(path)


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


def _failed_dossier(store: DossierStore, job_id: str, domain: str, exc: Exception):
    dossier = store.create(job_id=job_id, domain=domain)
    dossier.mark_phase("system", "error")
    dossier.evidence["error"] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    store.save(dossier)
    return dossier


def _project_status(dossier: Any, run_dir: Path) -> dict[str, Any]:
    contract = _read_json(run_dir / "research_contract.input.json") or {}
    review = _read_json(run_dir / "quality_review_round1.json") or {}
    status = _status(dossier.phases)
    artifacts = _artifact_projection(dossier)
    has_pdf = bool(artifacts.get("has_pdf"))
    delivery = review.get("delivery")
    if delivery is None and status == "done":
        delivery = "pass" if has_pdf and not _has_blocking_gate(dossier) else None

    return {
        "tier": contract.get("level") or contract.get("tier"),
        "research_plan": {
            "topic": contract.get("topic"),
            "research_question": contract.get("research_question"),
            "contribution": contract.get("contribution"),
        },
        "b_gap": contract.get("b_gap"),
        "a_gap": _phase_gap(run_dir),
        "viability": dossier.evidence.get("viability"),
        "summary": {
            "floor_100": review.get("floor_100"),
            "delivery": delivery,
            "phases_done": [phase for phase, phase_status in dossier.phases.items() if phase_status == "done"],
        },
        "artifacts": artifacts,
    }


def _artifact_projection(dossier: Any) -> dict[str, Any]:
    projected = {
        name: {
            "path": ref.path,
            "sha256": ref.sha256,
            "url": _artifact_url(dossier.job_id, name),
        }
        for name, ref in dossier.artifacts.items()
    }
    has_pdf = "paper_draft_v0.pdf" in dossier.artifacts
    projected["has_pdf"] = has_pdf
    projected["pdf"] = _artifact_url(dossier.job_id, "paper_draft_v0.pdf") if has_pdf else None
    return projected


def _artifact_url(job_id: str, artifact_id: str) -> str:
    encoded = "/".join(quote(part, safe="") for part in artifact_id.split("/"))
    return f"/v3/jobs/{job_id}/artifact/{encoded}"


def _phase_gap(run_dir: Path) -> list[dict[str, str]]:
    path = run_dir / "phase3_positioning.md"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    return [{"description": text}] if text else []


def _has_blocking_gate(dossier: Any) -> bool:
    for report in dossier.gate_reports:
        if report.get("blocked"):
            return True
    return False


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


def _jsonable(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        data = asdict(value)
    elif isinstance(value, dict):
        data = value
    else:
        raise TypeError("value is not JSON object shaped: %s" % type(value).__name__)
    return dict(data)


def _indexed_artifact_path(run_dir: Path, artifact_path: str) -> Path:
    base = run_dir.resolve()
    path = (run_dir / artifact_path).resolve()
    try:
        path.relative_to(base)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="artifact not found") from exc
    return path
