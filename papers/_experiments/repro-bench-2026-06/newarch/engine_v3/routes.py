from __future__ import annotations

import hashlib
import json
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

    async def _json(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="body must be a JSON object")
        return payload

    @app.post("/v3/jobs", status_code=202)
    async def create_v3_job(
        request: Request,
        response: Response,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ) -> dict[str, Any]:
        _require_post_auth(authorization, auth_token)
        contract = await _json(request)
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

        run_dir.mkdir(parents=True, exist_ok=True)
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
        return {
            "engine": "v3",
            "job_id": job_id,
            "status": _status(dossier.phases),
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
    if authorization != "Bearer %s" % auth_token:
        raise HTTPException(status_code=401, detail="invalid bearer token")


def _job_id(contract: dict[str, Any]) -> str:
    blob = json.dumps(contract, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "v3_" + hashlib.sha256(blob).hexdigest()[:12]


def _status(phases: dict[str, str]) -> str:
    if not phases:
        return "accepted"
    if any(status == "error" for status in phases.values()):
        return "failed"
    if any(status == "blocked" for status in phases.values()):
        return "blocked"
    return "done"
