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


def _read_json_or_warn(path: Path) -> tuple[dict[str, Any], Optional[str]]:
    """Distinguish MISSING (normal while a run is still producing it) from CORRUPT (a real
    failure worth surfacing) — a done job with an unreadable result must not look like a
    job that simply has no result."""
    if not path.is_file():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (data if isinstance(data, dict) else {}), None
    except Exception as exc:  # noqa: BLE001
        return {}, f"{path.name} 無法解析（{type(exc).__name__}）"


# scales whose no-effect NULL is 0 (CI crossing 0 -> not significant). log_ratio is on
# the log scale so its null is also 0. A raw ratio / prevalence / proportion scale would
# need a different null, so significance is asserted ONLY for these — never guessed.
_ZERO_NULL_SCALES = {"smd", "md", "smcc", "rd", "log_ratio", "logor", "logrr", "z", "cohen_d", "hedges_g"}


def _phase3_gaps(run_dir: Path) -> list[dict[str, str]]:
    """FALLBACK for OLD runs whose dossier predates structured-gap storage: the pipeline
    now stores structured gaps in dossier.claims.research_gaps up-front; for older runs we
    re-parse the phase3 markdown with the SAME shared parser (no logic drift)."""
    md = Path(run_dir) / "phase3_positioning.md"
    if not md.is_file():
        return []
    from packs.paper import gaps as _gaps
    return _gaps.parse_gap_matrix(md.read_text(encoding="utf-8", errors="ignore"))


def _dataset_key_result(rr: dict[str, Any]) -> dict[str, Any]:
    """Dataset lane: surface the PRIMARY model HONESTLY (including a null) — never
    cherry-pick a significant descriptive model over the rigorous primary specification.
    Picks the model the analysis flags primary (id/family containing 'primary', else a
    fixed-effects/within spec, else the most-adjusted). is_significant reported as-is, so
    a non-significant primary result (e.g. attenuated TWFE) shows as not significant."""
    try:
        import dataset_lane.schema as _ds_schema
        primary = _ds_schema.primary_model(rr)        # reads the DECLARATION, not a string guess
    except Exception:  # noqa: BLE001 - report card must never crash the status endpoint
        primary = {}
    if not primary:
        return {}
    est = primary.get("estimate")
    if est is None:
        est = primary.get("beta")
    lo, hi, p = primary.get("ci_low"), primary.get("ci_high"), primary.get("p_value")
    is_sig: Any = None
    if isinstance(p, (int, float)):
        is_sig = p < 0.05
    elif isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        is_sig = not (lo <= 0 <= hi)
    return {"lane": "dataset", "model": primary.get("id") or primary.get("family"),
            "outcome": primary.get("outcome"), "exposure": primary.get("exposure"),
            "estimate": est, "ci_low": lo, "ci_high": hi, "p_value": p,
            "is_significant": is_sig}


def _key_result(rr: dict[str, Any]) -> dict[str, Any]:
    """The ACTUAL finding (parsed real_results) for the result card + the pooled-effects
    count. GENERAL across synthesis scales: pick the PRIMARY pooled scale the SAME way the
    engine does — most pooled EFFECTS (meta_analysis.py `max(poolable, key=len)`), with a
    deterministic scale-name tie-break — never hardcode SMD. Distinguishes EFFECTS (k) from
    STUDIES (studies_with_effects); asserts significance ONLY for zero-null scales. Returns
    {} for non-meta runs (no `meta.pooled`) so the card simply hides."""
    meta = rr.get("meta", {}) if isinstance(rr, dict) else {}
    pooled = meta.get("pooled") or {}
    prisma = meta.get("prisma") or {}
    scales = {s: v for s, v in pooled.items() if isinstance(v, dict) and v.get("pooled_effect") is not None}
    if not scales:
        return _dataset_key_result(rr)      # dataset lane: surface the PRIMARY model honestly
    primary = max(scales, key=lambda s: (scales[s].get("k") or 0, s))   # most effects; deterministic tie-break
    p = scales[primary]
    scale = (p.get("scale") or primary)
    lo, hi = p.get("ci_low"), p.get("ci_high")
    is_sig: Any = None
    if str(scale).lower() in _ZERO_NULL_SCALES and isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        is_sig = not (lo <= 0 <= hi)                          # CI excludes the null (0) -> significant
    return {"scale": scale, "k_effects": p.get("k"),
            "n_studies": prisma.get("studies_with_effects"),
            "n_identified": prisma.get("identified"),
            "pooled_effect": p.get("pooled_effect"), "ci_low": lo, "ci_high": hi,
            "i2_percent": p.get("i2_percent"), "is_significant": is_sig}


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
    rr, rr_warn = _read_json_or_warn(Path(run_dir) / "real_experiments" / "real_results.json")

    a_gap = claims.get("research_gaps") or _phase3_gaps(run_dir)
    key_result = _key_result(rr)
    run_status = _run_status(dossier_data)
    has_result = result.get("floor_100") is not None
    # honest terminal state: 'done' must have a real run_result; otherwise it finished
    # without a deliverable — surface 'incomplete', don't show 完成 with everything blank.
    if run_status == "done" and not has_result:
        run_status = "incomplete"
    return {
        "engine": "v2",
        "job_id": dossier_data.get("run", {}).get("job_id"),
        "status": run_status,
        "phase": status.get("phase"),
        "checkpoint": status.get("checkpoint"),
        "blocked": status.get("blocked", False),
        "blockers": status.get("blockers", []),
        "tier": contract.get("level"),
        "lane": rr.get("lane"),
        "synthesis_type": rr.get("synthesis_type") or (rr.get("meta") or {}).get("synthesis_type"),
        "output_language": contract.get("output_language"),
        "research_plan": {"topic": contract.get("topic"),
                          "research_question": contract.get("research_question"),
                          "contribution": contract.get("contribution")},
        # b_gap = the grill's gap ONLY (nullable). Do NOT fall back to the contribution/RQ —
        # that would mislabel the research aim as a 'gap' for a direct (no-grill) submit.
        "b_gap": claims.get("b_gap"),
        "a_gap": a_gap,
        # viability = the REAL viability decision (nullable). pooled_k is a DATA-EXTENT fact
        # (how many effects were pooled), NOT a viability verdict — never fabricate viable.
        "viability": {"viable": viability.get("viable"), "metric": viability.get("metric"),
                      "pooled_k": key_result.get("k_effects"),
                      "pending_confirmation": dossier_data.get("pending_confirmation")},
        "key_result": key_result or None,
        "summary": {"floor_100": result.get("floor_100"), "delivery": result.get("delivery"),
                    "phases_done": result.get("phases_done")},
        "artifacts": {"has_pdf": pdf.is_file()},   # bool flag — no server path leak; page derives /paper
        "error": ext.get("run_error"),
        "data_warning": rr_warn,                    # set only when real_results exists but is unreadable
        "degraded": dossier_data.get("degraded") or None,  # phases that fell back (codex limit -> big-pickle)
        "research_value": dossier_data.get("research_value") or None,  # Gate E: a-side value confirmation
        # analysis-design issues the review surfaced but could NOT auto-fix (need a re-run /
        # spec change) — shown on the page so the user sees them, not silently dropped.
        "analysis_findings": dossier_data.get("analysis_findings") or None,
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
