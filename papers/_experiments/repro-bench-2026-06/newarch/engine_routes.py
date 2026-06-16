"""Engine-v2 HTTP routes (ENGINE_BUILD_PLAN P7 / DESIGN §5.3; codex review 2026-06-16).

`POST /v2/jobs` initialises the dossier and DETACHES a `v2_worker` subprocess that runs
the full `pipeline.run_paper` (codex brain + free big-pickle worker), returning a job_id
in <1s. The worker survives a uvicorn redeploy (`start_new_session` + `KillMode=process`)
and marks the dossier `failed` on any crash. `GET /v2/jobs/{id}/status` returns the
enriched dossier projection (research plan, b-gap, a-gap, tier, phase progress, terminal
status, PDF link). The old paper_driver pipeline on `/jobs` is untouched (A/B).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, Header, HTTPException, Request, Response

from framework import Dossier
from packs.insurance import InsurancePack
from packs.paper import PaperPack

PACKS = {"paper": PaperPack, "insurance": InsurancePack}
HERE = Path(__file__).resolve().parent
# fields chat.ai must NOT set (server-decided; SYSTEM_SPEC_v2 §5) — thin-handoff guard
CHAT_FORBIDDEN_FIELDS = ("level", "tier", "source", "target_journal")


def _pack_for(contract: dict[str, Any]):
    src = str(contract.get("source") or "").lower()
    domain = "insurance" if "insurance" in src else contract.get("domain", "paper")
    return PACKS.get(domain, PaperPack)()


def _job_id(contract: dict[str, Any]) -> str:
    blob = json.dumps(contract, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "v2_" + hashlib.sha256(blob).hexdigest()[:12]


def _default_spawn(run_dir: Path) -> None:
    """Detach the v2_worker as a fresh-session subprocess (survives KillMode=process)."""
    log = (run_dir / "v2_worker.log").open("ab")
    subprocess.Popen([sys.executable, str(HERE / "v2_worker.py"), str(run_dir)],
                     cwd=str(HERE), start_new_session=True, stdout=log, stderr=subprocess.STDOUT)


def _run_status(dossier_data: dict[str, Any]) -> str:
    st = dossier_data.get("status", {})
    rs = st.get("run_status")
    if rs:
        return rs                                   # running | done | blocked | failed
    return "submitted" if st.get("phase") in (None, "start") else "running"


def project_status(dossier_data: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """The projection the live page reads (§5.3): research plan, b-gap, a-gap, tier,
    phase progress, terminal status + PDF link (codex: was too thin)."""
    status = dossier_data.get("status", {})
    claims = dossier_data.get("claims", {})
    contract = dossier_data.get("contract", {})
    viability = dossier_data.get("viability", {})
    ext = dossier_data.get("pack_ext", {})
    result = ext.get("run_result") or {}
    pdf = Path(run_dir) / "paper_draft_v0.pdf"
    return {
        "engine": "v2",
        "job_id": dossier_data.get("run", {}).get("job_id"),
        "status": _run_status(dossier_data),
        "phase": status.get("phase"),
        "checkpoint": status.get("checkpoint"),
        "blocked": status.get("blocked", False),
        "blockers": status.get("blockers", []),
        "tier": contract.get("level"),
        "research_plan": {"topic": contract.get("topic"),
                          "research_question": contract.get("research_question"),
                          "contribution": contract.get("contribution")},
        # b-gap = the grill's gap; for a live run_paper (no intake phase) fall back to
        # the contract's contribution/question so the page always shows the b-side gap.
        "b_gap": claims.get("b_gap") or contract.get("contribution") or contract.get("research_question"),
        "a_gap": claims.get("research_gaps", []),
        "viability": {"viable": viability.get("viable"), "metric": viability.get("metric"),
                      "pending_confirmation": dossier_data.get("pending_confirmation")},
        "summary": {"floor_100": result.get("floor_100"), "delivery": result.get("delivery"),
                    "phases_done": result.get("phases_done")},
        "artifacts": {"pdf": str(pdf) if pdf.is_file() else None},
        "error": ext.get("run_error"),
        "updated_at": status.get("finished_at") or status.get("started_at"),
    }


def register(app: FastAPI, jobs_dir: Path, *,
             spawn: Callable[[Path], None] = _default_spawn, max_concurrent: int = 1) -> None:
    jobs_dir = jobs_dir.expanduser().resolve()

    def _run_dir(job_id: str) -> Path:
        return jobs_dir / job_id / "run"

    def _live_count() -> int:
        n = 0
        for dj in jobs_dir.glob("v2_*/run/dossier.json"):
            try:
                if _run_status(json.loads(dj.read_text(encoding="utf-8"))) == "running":
                    n += 1
            except (OSError, json.JSONDecodeError):
                pass
        return n

    async def _json(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="body must be a JSON object")
        return payload

    @app.post("/v2/jobs", status_code=202)
    async def create_v2_job(request: Request, response: Response,
                            idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key")
                            ) -> dict[str, Any]:
        contract = await _json(request)
        job_id = _job_id(contract)
        run_dir = _run_dir(job_id)
        status_url = f"/v2/jobs/{job_id}/status"

        # Idempotent replay: a deterministic job_id means a duplicate submit must NOT
        # clobber an existing run dir — return the in-flight/finished job instead (codex).
        if (run_dir / "dossier.json").is_file():
            response.status_code = 200
            return {"job_id": job_id, "engine": "v2", "status": "idempotent_replay",
                    "status_url": status_url}

        if _live_count() >= max_concurrent:           # ac-2012 runs codex/hermes serially
            raise HTTPException(status_code=429,
                                detail=f"engine busy ({max_concurrent} concurrent v2 job max); retry later")

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "research_contract.json").write_text(
            json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        Dossier.create(run_dir, job_id, contract, mode=_pack_for(contract).name)
        spawn(run_dir)                                # detach the full pipeline; return immediately
        return {"job_id": job_id, "engine": "v2", "status": "accepted", "status_url": status_url}

    @app.get("/v2/jobs/{job_id}/status")
    def get_v2_status(job_id: str) -> dict[str, Any]:
        dossier_path = _run_dir(job_id) / "dossier.json"
        if not dossier_path.is_file():
            raise HTTPException(status_code=404, detail=f"no v2 job: {job_id}")
        data = json.loads(dossier_path.read_text(encoding="utf-8"))
        return project_status(data, _run_dir(job_id))
