"""Engine-v2 HTTP routes (ENGINE_BUILD_PLAN P7 / DESIGN §5.3).

Mounts the NEW orchestrator path alongside the old pipeline (A/B — never churn
production around an unproven orchestrator). `POST /v2/jobs` routes to the framework
Orchestrator (not paper_driver's old loop); `GET /v2/jobs/{id}/status` returns the
DOSSIER PROJECTION (research plan, b-gap, a-gap, tier decision, live phase progress)
— not the coarse job status.

The reasoning loop (Phases 1-11) runs on ac-2012 with the live brain; here the route
creates the run + dossier and exposes its projection. The dispatcher is injected so
the service is testable offline (MockDispatcher) and live (HermesDispatcher).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request

from framework import Dispatcher, Orchestrator, Phase
from packs.insurance import InsurancePack
from packs.paper import PaperPack

PACKS = {"paper": PaperPack, "insurance": InsurancePack}


def _pack_for(contract: dict[str, Any]):
    src = str(contract.get("source") or "").lower()
    domain = "insurance" if "insurance" in src else "paper"
    domain = contract.get("domain", domain)
    return PACKS.get(domain, PaperPack)()


def _job_id(contract: dict[str, Any]) -> str:
    blob = json.dumps(contract, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "v2_" + hashlib.sha256(blob).hexdigest()[:12]


def _intake_phases() -> list[Phase]:
    """The bounded intake the service runs synchronously: record the research plan +
    the b-side gap into the dossier and checkpoint. The full 11-phase reasoning loop
    is dispatched to the live brain on ac-2012 (a separate worker)."""
    def record_plan(o: Orchestrator) -> None:
        c = o.dossier.data.get("contract", {})
        o.dossier.set("claims", {**o.dossier.data.get("claims", {}),
                                 "b_gap": c.get("contribution") or c.get("research_question"),
                                 "research_gaps": o.dossier.data.get("claims", {}).get("research_gaps", [])})
    return [Phase("intake", record_plan, checkpoint_artifacts=[])]


def project_status(dossier_data: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """The dossier projection the live project page reads (§5.3): research plan,
    b-gap, a-gap, tier decision, phase progress."""
    status = dossier_data.get("status", {})
    claims = dossier_data.get("claims", {})
    contract = dossier_data.get("contract", {})
    viability = dossier_data.get("viability", {})
    return {
        "engine": "v2",
        "job_id": dossier_data.get("run", {}).get("job_id"),
        "phase": status.get("phase"),
        "checkpoint": status.get("checkpoint"),
        "blocked": status.get("blocked", False),
        "blockers": status.get("blockers", []),
        "tier": contract.get("level"),                       # tier decision
        "research_plan": {"topic": contract.get("topic"),
                          "research_question": contract.get("research_question"),
                          "contribution": contract.get("contribution")},
        "b_gap": claims.get("b_gap"),                        # gap the grill determined
        "a_gap": claims.get("research_gaps", []),            # phase0/phase3 gap (may refine b's)
        "viability": {"viable": viability.get("viable"),
                      "metric": viability.get("metric"),
                      "pending_confirmation": dossier_data.get("pending_confirmation")},
        "revision_loop": dossier_data.get("revision_loop", {}),
        "delegations": len(dossier_data.get("delegations", [])),
    }


def register(app: FastAPI, jobs_dir: Path, dispatcher: Dispatcher) -> None:
    jobs_dir = jobs_dir.expanduser().resolve()

    async def _json(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=422, detail="body must be a JSON object")
        return payload

    def _run_dir(job_id: str) -> Path:
        return jobs_dir / job_id / "run"

    @app.post("/v2/jobs", status_code=202)
    async def create_v2_job(request: Request) -> dict[str, Any]:
        contract = await _json(request)
        pack = _pack_for(contract)
        job_id = _job_id(contract)
        run_dir = _run_dir(job_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "research_contract.json").write_text(
            json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        # The NEW orchestrator drives the run (not paper_driver's old loop).
        orch = Orchestrator(run_dir, pack, dispatcher, _intake_phases(),
                            job_id=job_id, contract=contract)
        orch.run()
        return {"job_id": job_id, "engine": "v2", "status": "accepted",
                "run_dir": str(run_dir),
                "status_url": f"/v2/jobs/{job_id}/status"}

    @app.get("/v2/jobs/{job_id}/status")
    def get_v2_status(job_id: str) -> dict[str, Any]:
        dossier_path = _run_dir(job_id) / "dossier.json"
        if not dossier_path.is_file():
            raise HTTPException(status_code=404, detail=f"no v2 job: {job_id}")
        data = json.loads(dossier_path.read_text(encoding="utf-8"))
        return project_status(data, _run_dir(job_id))
