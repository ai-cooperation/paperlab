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


def _read_json_safe(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _phase3_gaps(run_dir: Path) -> list[str]:
    """Surface the gaps the engine actually WROTE (phase3_positioning.md Gap Matrix).
    The run_paper lane writes the gap to a file, not to dossier.claims.research_gaps, so
    the projection looked empty ('尚未判定') even though the engine produced a full gap
    analysis. Parse the Gap column of the markdown table."""
    md = Path(run_dir) / "phase3_positioning.md"
    if not md.is_file():
        return []
    gaps: list[str] = []
    in_matrix = False
    for line in md.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if s.startswith("## ") and "Gap Matrix" in s:
            in_matrix = True
            continue
        if in_matrix and s.startswith("## "):
            break
        if in_matrix and s.startswith("|"):
            first = s.strip("|").split("|")[0].strip()
            if first and first.lower() != "gap" and set(first) - set("-: "):
                gaps.append(first)
    return gaps[:5]


def _key_result(run_dir: Path) -> dict[str, Any]:
    """The ACTUAL finding (real_results) for a result card + the pooled-k for data
    feasibility — language-neutral numbers the page shows even for an English paper."""
    rr = _read_json_safe(Path(run_dir) / "real_experiments" / "real_results.json")
    meta = rr.get("meta", {}) if isinstance(rr, dict) else {}
    pooled = (meta.get("pooled") or {}).get("smd") or {}
    prisma = meta.get("prisma") or {}
    if not pooled:
        return {}
    return {"scale": pooled.get("scale"), "k": pooled.get("k"),
            "pooled_effect": pooled.get("pooled_effect"),
            "ci_low": pooled.get("ci_low"), "ci_high": pooled.get("ci_high"),
            "i2_percent": pooled.get("i2_percent"),
            "studies_with_effects": prisma.get("studies_with_effects"),
            "identified": prisma.get("identified")}


def project_status(dossier_data: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """The projection the live page reads (§5.3): research plan, b-gap, a-gap, tier,
    phase progress, terminal status + PDF link. Enriched to surface what the engine
    actually PRODUCED (phase3 gaps, pooled result, pooled-k) — not just echo the input
    contract (the page looked thin/incomplete for a finished 70.8 run)."""
    status = dossier_data.get("status", {})
    claims = dossier_data.get("claims", {})
    contract = dossier_data.get("contract", {})
    viability = dossier_data.get("viability", {})
    ext = dossier_data.get("pack_ext", {})
    result = ext.get("run_result") or {}
    pdf = Path(run_dir) / "paper_draft_v0.pdf"

    a_gap = claims.get("research_gaps") or _phase3_gaps(run_dir)
    key_result = _key_result(run_dir)
    # data feasibility: the run_paper lane has no intake-viability phase, but the meta
    # analysis DID pool k effects — surface that real k so the page isn't blank ('—').
    via_metric = viability.get("metric")
    via_viable = viability.get("viable")
    if via_metric is None and key_result.get("k"):
        via_metric = {"max_poolable_k": key_result["k"]}
        via_viable = True if via_viable is None else via_viable
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
        "a_gap": a_gap,
        "viability": {"viable": via_viable, "metric": via_metric,
                      "pending_confirmation": dossier_data.get("pending_confirmation")},
        "key_result": key_result or None,
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
        try:                                          # reuse the viability-probe corpus (no re-collect)
            import viability_service
            viability_service.seed_run_corpus(jobs_dir, contract, run_dir)
        except Exception:  # noqa: BLE001 - a missing cache just means run_paper collects fresh
            pass
        spawn(run_dir)                                # detach the full pipeline; return immediately
        return {"job_id": job_id, "engine": "v2", "status": "accepted", "status_url": status_url}

    @app.post("/jobs/viability-probe")
    async def viability_probe(request: Request) -> dict[str, Any]:
        # Collect/cache the corpus by contract_hash + run handle_viability; returns the
        # lockable verdict + the a-side-authoritative contract_hash (b stores it). The
        # grill calls this early; submit re-uses the cached corpus. (~1-2 min on a cold
        # scope; instant on a cache hit.)
        contract = await _json(request)
        import viability_service
        try:
            return viability_service.probe(jobs_dir, contract)
        except Exception as exc:  # noqa: BLE001 - surface a structured error, never fake viable
            raise HTTPException(status_code=502, detail=f"viability probe failed: {exc}") from exc

    @app.get("/v2/jobs/{job_id}/status")
    def get_v2_status(job_id: str) -> dict[str, Any]:
        dossier_path = _run_dir(job_id) / "dossier.json"
        if not dossier_path.is_file():
            raise HTTPException(status_code=404, detail=f"no v2 job: {job_id}")
        data = json.loads(dossier_path.read_text(encoding="utf-8"))
        return project_status(data, _run_dir(job_id))

    @app.get("/v2/jobs/{job_id}/paper")
    def get_v2_paper(job_id: str):
        """Serve the rendered PDF for download (the live page links here when done)."""
        from fastapi.responses import FileResponse
        pdf = _run_dir(job_id) / "paper_draft_v0.pdf"
        if not pdf.is_file():
            raise HTTPException(status_code=404, detail=f"no paper for v2 job: {job_id}")
        return FileResponse(str(pdf), media_type="application/pdf",
                            filename=f"{job_id}_paper.pdf")
