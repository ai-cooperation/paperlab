#!/usr/bin/env python3
"""Async-friendly JSON job runner for the validated new-architecture pipeline."""
from __future__ import annotations

import argparse
import base64
import datetime as dt
from email.message import EmailMessage
import json
import os
import smtplib
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

import data_availability_gate
import router
import source_probe


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JOBS_DIR = SCRIPT_DIR / "jobs"
RUNNER_VERSION = "2026-06-06-a"
BLOCKED_EXIT = 3   # paper_driver exit code for a deterministic block (terminal; no retry)

OUTPUT_KEYS = (
    "job_id",
    "status",
    "review_status",
    "score_source",
    "run_dir",
    "level",
    "content_score",
    "content_threshold",
    "meets_threshold",
    "desk_reject",
    "above_5_5",
    "gates",
    "doi_real_rate",
    "delivery_audit",
    "pdf_path",
    "real_vs_simulated",
    "blockers",
)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def job_dir_for(job_id: str, jobs_dir: Path) -> Path:
    if not job_id or "/" in job_id or job_id in {".", ".."}:
        raise ValueError(f"unsafe job_id: {job_id!r}")
    return jobs_dir.expanduser().resolve() / job_id


def load_contract(contract_path: Path) -> dict[str, Any]:
    payload = read_json(contract_path)
    if not isinstance(payload, dict):
        raise ValueError("research_contract.json must contain a JSON object")
    router.validate_contract(payload)
    return payload


def initial_state(job_id: str, contract: dict[str, Any], routing_decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "runner_version": RUNNER_VERSION,
        "status": "submitted",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "source": contract["source"],
        "level": contract["level"],
        "tier": contract["tier"],
        "topic": contract["topic"],
        "routing_decision": routing_decision,
        "history": [{"status": "submitted", "at": now_iso(), "note": "job accepted"}],
        "run_dir": None,
        "worker_pid": None,
        "repo_url": contract.get("repo_url"),
        "notification": None,
        "repo_sync": None,
        "output": None,
    }


def write_state(job_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json(job_dir / "state.json", state)


def update_state(job_dir: Path, status_value: str, note: str = "", **updates: Any) -> dict[str, Any]:
    state = read_json(job_dir / "state.json", {})
    state.update(updates)
    state["status"] = status_value
    state.setdefault("history", []).append({"status": status_value, "at": now_iso(), "note": note})
    write_state(job_dir, state)
    return state


def submit(contract_path: Path, jobs_dir: Path = DEFAULT_JOBS_DIR, start_worker: bool = True) -> dict[str, Any]:
    contract = load_contract(contract_path)
    job_id = str(contract["job_id"]).strip()
    job_dir = job_dir_for(job_id, jobs_dir)
    if job_dir.exists() and (job_dir / "state.json").exists():
        raise FileExistsError(f"job already exists: {job_id}")
    job_dir.mkdir(parents=True, exist_ok=True)
    routing_decision = router.route_contract(contract)
    write_json(job_dir / "contract.json", contract)
    write_json(job_dir / "routing_decision.json", routing_decision)
    state = initial_state(job_id, contract, routing_decision)
    write_state(job_dir, state)
    if start_worker:
        log = (job_dir / "worker.log").open("ab")
        proc = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "worker",
                "--job-id",
                job_id,
                "--jobs-dir",
                str(jobs_dir.expanduser().resolve()),
            ],
            cwd=SCRIPT_DIR,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        state["worker_pid"] = proc.pid
        write_state(job_dir, state)
    return {"job_id": job_id, "status": "submitted", "state_path": str(job_dir / "state.json")}


def status(job_id: str, jobs_dir: Path = DEFAULT_JOBS_DIR) -> dict[str, Any]:
    job_dir = job_dir_for(job_id, jobs_dir)
    state = read_json(job_dir / "state.json")
    if not isinstance(state, dict):
        raise FileNotFoundError(f"unknown job_id: {job_id}")
    return state


def result(job_id: str, jobs_dir: Path = DEFAULT_JOBS_DIR) -> dict[str, Any]:
    state = status(job_id, jobs_dir)
    output = state.get("output")
    if isinstance(output, dict):
        return output
    output_path = job_dir_for(job_id, jobs_dir) / "output.json"
    output = read_json(output_path)
    if isinstance(output, dict):
        return output
    return {
        "job_id": job_id,
        "status": state.get("status"),
        "run_dir": state.get("run_dir"),
        "level": state.get("routing_decision", {}).get("level") if isinstance(state.get("routing_decision"), dict) else None,
        "content_score": None,
        "content_threshold": (
            state.get("routing_decision", {}).get("content_threshold")
            if isinstance(state.get("routing_decision"), dict)
            else None
        ),
        "meets_threshold": False,
        "desk_reject": None,
        "above_5_5": False,
        "gates": {},
        "doi_real_rate": None,
        "pdf_path": None,
        "real_vs_simulated": {},
        "blockers": ["job has not produced an output yet"],
    }


def normalized_source_name(data_source: dict[str, Any]) -> str:
    return " ".join(str(data_source.get("name") or "").lower().replace("/", " ").split())


def probe_data_source(contract: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Run-time data gate, conditional on data_source.type (still fail-closed):
    - literature  -> OpenAlex corpus confirm (universal: any topic with a real
                     corpus passes; the scientometric lane collects + analyses it)
    - dataset HUPD -> full schema probe + the classical-ML experiment lane
    - dataset other -> blocked with an actionable reason (generic dataset
                     EXECUTION lane not implemented yet; the grill-time probe
                     endpoint can confirm reachability, but a cannot run it)
    """
    data_source = contract.get("data_source")
    if not isinstance(data_source, dict):
        return blocked_lock(run_dir, "data_source must be an object")
    ds_type = str(data_source.get("type") or "").lower()
    if ds_type in ("literature", "meta-analysis", "meta_analysis"):
        return source_probe.probe(contract, run_dir)
    if data_source.get("probe_required") is not True:
        return blocked_lock(run_dir, "data_source.probe_required must be true; job service is fail-closed")
    if ds_type != "dataset":
        return blocked_lock(run_dir, f"unsupported data_source.type={data_source.get('type')!r}")
    name = normalized_source_name(data_source)
    if "hupd" not in name and "harvard uspto patent dataset" not in name:
        return blocked_lock(
            run_dir,
            f"data_source {data_source.get('name')!r} has no execution lane on this runner yet "
            "(registered dataset lanes: HUPD). Use the literature lane (type=literature) for "
            "any-topic scientometric analysis, or a registered dataset.",
        )
    return data_availability_gate.probe_hupd(run_dir, sample_rows=160)


def blocked_lock(run_dir: Path, reason: str) -> dict[str, Any]:
    payload = {
        "source": "unknown",
        "type": "dataset",
        "status": "unavailable",
        "sample_evidence": {"error_type": "UnsupportedDataSource"},
        "reason": reason,
        "generated_at_unix": round(time.time(), 3),
        "probe_seconds": 0.0,
    }
    write_json(run_dir / "data_source_lock.json", payload)
    return payload


def threshold_fields(
    routing_decision: dict[str, Any] | None,
    score_float: float | None,
    no_p0: bool = True,
) -> dict[str, Any]:
    decision = routing_decision if isinstance(routing_decision, dict) else {}
    threshold = decision.get("content_threshold")
    try:
        threshold_float = float(threshold)
    except (TypeError, ValueError):
        threshold_float = None
    return {
        "level": decision.get("level"),
        "content_threshold": threshold_float,
        # Aligned with compile_review: meeting the bar requires score >= threshold
        # AND zero P0 problems (the revision loop is what drives P0 -> 0).
        "meets_threshold": bool(
            score_float is not None
            and threshold_float is not None
            and score_float >= threshold_float
            and no_p0
        ),
    }


def blocked_output(job_id: str, run_dir: Path, lock: dict[str, Any], routing_decision: dict[str, Any] | None = None) -> dict[str, Any]:
    reason = lock.get("reason") or "data source unavailable"
    return {
        "job_id": job_id,
        "status": "blocked",
        "run_dir": str(run_dir),
        **threshold_fields(routing_decision, None),
        "content_score": None,
        "desk_reject": None,
        "above_5_5": False,
        "gates": {"data_availability": lock},
        "doi_real_rate": None,
        "pdf_path": None,
        "real_vs_simulated": {"real_status": "not_run", "simulated": False},
        "blockers": [f"DATA-AVAILABILITY gate failed closed: {reason}"],
    }


def derive_lane(routing_decision: dict[str, Any], contract: dict[str, Any] | None = None) -> str:
    """paper_driver lane: cpu-real whenever real data is available (the data gate
    has already passed by the time run_pipeline runs), else mvp/simulated.
    A literature data source is REAL data (the OpenAlex corpus the gate just
    confirmed) — the scientometric lane collects + analyses it, never ^S^."""
    ds_type = str(((contract or {}).get("data_source") or {}).get("type") or "").lower()
    if ds_type in ("literature", "meta-analysis", "meta_analysis"):
        return "cpu-real"
    if routing_decision.get("needs_real_experiment_lane"):
        return "cpu-real"
    if "real" in str(routing_decision.get("lane") or "").lower():
        return "cpu-real"
    return "mvp"


def run_pipeline(job_dir: Path, run_dir: Path, routing_decision: dict[str, Any]) -> list[dict[str, Any]]:
    """Route A: dispatch the real Hermes phasefix driver (paper_driver.py).

    Replaces the mock run_newarch.py. paper_driver internally runs the real
    paper-draft phases, the DOI anti-cheat gate, and the real 3-layer review,
    emitting the artifact contract extract_output() reads.
    """
    attempts: list[dict[str, Any]] = []
    fallback = routing_decision.get("fallback_policy", {})
    max_attempts = int(fallback.get("max_attempts_per_model") or 1)
    timeout = int(routing_decision.get("timeout_seconds") or 21600)
    contract = read_json(job_dir / "contract.json")
    lane = derive_lane(routing_decision, contract if isinstance(contract, dict) else None)
    review_depth = str(routing_decision.get("review_depth") or "7dim")
    content_threshold = routing_decision.get("content_threshold") or 6.0
    if str(routing_decision.get("driver") or "hermes") != "hermes":
        # Only the hermes phasefix driver is implemented; treat anything else as hermes.
        pass
    for model in routing_decision.get("model_chain", []):
        for attempt in range(1, max_attempts + 1):
            started = time.time()
            log_path = job_dir / f"pipeline_{model}_attempt{attempt}.log"
            cmd = [
                sys.executable,
                str(SCRIPT_DIR / "paper_driver.py"),
                "--run-dir",
                str(run_dir),
                "--model",
                str(model),
                "--lane",
                lane,
                "--review-depth",
                review_depth,
                "--content-threshold",
                str(content_threshold),
                "--max-revision-rounds",
                str(routing_decision.get("max_revision_rounds") or 2),
                "--real-limit",
                "2000",
            ]
            with log_path.open("ab") as log:
                proc = subprocess.run(
                    cmd,
                    cwd=SCRIPT_DIR,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                )
            entry = {
                "model": model,
                "attempt": attempt,
                "returncode": proc.returncode,
                "seconds": round(time.time() - started, 3),
                "log_path": str(log_path),
            }
            attempts.append(entry)
            if proc.returncode == 0:
                return attempts
            if proc.returncode == BLOCKED_EXIT:
                # Deterministic block (non-viable plan / too few studies / DOI gate):
                # retrying or switching model cannot help -> terminal, stop now.
                entry["terminal_block"] = True
                return attempts
        if not fallback.get("paid_fallback"):
            return attempts
    return attempts


def read_artifacts(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    review = read_json(run_dir / "final_content_review_deterministic.json", {}) or {}
    gate = read_json(run_dir / "gate_report.json", {}) or {}
    trace = read_json(run_dir / "newarch_trace.json", {}) or {}
    real_result = read_json(run_dir / "real_experiments" / "real_results.json", {}) or {}
    refs = read_json(run_dir / "metadata.json", []) or []
    if not isinstance(review, dict):
        review = {}
    if not isinstance(gate, dict):
        gate = {}
    if not isinstance(trace, dict):
        trace = {}
    if not isinstance(real_result, dict):
        real_result = {}
    if not isinstance(refs, list):
        refs = []
    return review, gate, trace, real_result, refs


def doi_real_rate(refs: list[dict[str, Any]]) -> float | None:
    """CrossRef-real share over determinable refs. Mirrors doi_audit semantics:
    arXiv (DataCite) and no-DOI entries are excluded from the denominator —
    they are not determinable via CrossRef, not evidence of fabrication."""
    real_statuses = {"ok", "verified", "crossref_real"}
    skip_statuses = {"arxiv_datacite", "no_doi"}
    determinable = [r for r in refs if str(r.get("status") or "").lower() not in skip_statuses]
    if not determinable:
        return None
    verified = sum(1 for r in determinable if str(r.get("status") or "").lower() in real_statuses)
    return round(verified / len(determinable), 4)


def extract_output(
    job_id: str,
    run_dir: Path,
    blockers: list[str],
    routing_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review, gate, trace, real_result, refs = read_artifacts(run_dir)
    # Pre-delivery audit: the systematized human-QA filter. Consolidates the
    # render-quality gates + the defect classes only human review used to catch
    # (too-few refs, promise-vs-capability, subgroup-promise-gap, type mismatch).
    try:
        import delivery_audit
        audit_result = delivery_audit.audit(run_dir)
    except Exception as exc:  # noqa: BLE001 - audit must never crash finalization
        audit_result = {"verdict": "error", "p0_count": 0, "p1_count": 0,
                        "issues": [], "summary": f"audit error: {exc}"}
    content_score = review.get("mean_7dim") or trace.get("final_deterministic_score")
    desk_reject = (
        review.get("elite", {}).get("desk_reject_probability")
        if isinstance(review.get("elite"), dict)
        else None
    )
    if desk_reject is None:
        desk_reject = trace.get("final_desk_reject_probability") or gate.get("desk_reject_probability")
    pdf = run_dir / "paper_draft_v0.pdf"
    pdf_path = str(pdf) if pdf.is_file() and pdf.stat().st_size > 1000 else None
    problems = review.get("problems") if isinstance(review.get("problems"), list) else []
    job_blockers = list(blockers)
    for problem in problems:
        if isinstance(problem, dict) and problem.get("severity") in {"P0", "P1"}:
            job_blockers.append(str(problem.get("description") or problem.get("id")))
    for ai in audit_result.get("issues", []):
        if ai.get("severity") == "P0" and ai.get("type") == "delivery_audit":
            job_blockers.append(f"delivery-audit {ai.get('id')}: {ai.get('message')}")
    try:
        score_float = float(content_score)
    except (TypeError, ValueError):
        score_float = None
    no_p0 = review.get("p0_count", 0) == 0 if isinstance(review.get("p0_count"), int) else (gate.get("no_p0") is not False)
    # The public status enum stays submitted/running/done/blocked/failed; the review
    # nuance rides in `review_status` (scored | floor_only | model_review_pending).
    # When the model reviewer is down, the deterministic FLOOR still produces a score, so
    # the job completes `done` with review_status=floor_only (delivered + provisionally
    # scored, NOT certified — meets_threshold stays False until a real reviewer scores).
    score_source = str(review.get("score_source") or "model_reviewer")
    review_status = str(review.get("review_status") or ("scored" if score_float is not None else "model_review_pending"))
    if score_float is not None and pdf_path:
        status_value = "done"
    else:
        status_value = "failed"
    if review_status == "floor_only":
        job_blockers.append(
            "Scored by deterministic floor (model reviewer unavailable); delivered but "
            "NOT certified — real reviewer required to confirm it meets the bar."
        )
    output = {
        "job_id": job_id,
        "status": status_value,
        "review_status": review_status,
        "score_source": score_source,
        "run_dir": str(run_dir),
        **threshold_fields(routing_decision, score_float, no_p0),
        "content_score": score_float,
        "desk_reject": desk_reject,
        "above_5_5": bool(score_float is not None and score_float >= 5.5),
        "gates": {
            "data_availability": trace.get("data_availability_status") or gate.get("real_status"),
            "paper_gate_blocked": trace.get("gate_probe", {}).get("blocked") if isinstance(trace.get("gate_probe"), dict) else None,
            "no_p0": gate.get("no_p0") if "no_p0" in gate else review.get("p0_count") == 0 if "p0_count" in review else None,
            "p1_count": gate.get("p1_count", review.get("p1_count")),
            "real_status": trace.get("real_status") or gate.get("real_status"),
            "no_prose_skeleton": gate.get("no_prose_skeleton"),
            "prose_completeness_passed": gate.get("prose_completeness_passed"),
            "prose_total_words": gate.get("prose_total_words"),
        },
        "doi_real_rate": doi_real_rate(refs),
        "delivery_audit": {"verdict": audit_result.get("verdict"),
                           "p0_count": audit_result.get("p0_count"),
                           "p1_count": audit_result.get("p1_count"),
                           "summary": audit_result.get("summary")},
        "pdf_path": pdf_path,
        "real_vs_simulated": {
            "real_status": trace.get("real_status") or real_result.get("status"),
            "simulated_markers_final": trace.get("simulated_markers_final"),
            "simulation_markers": real_result.get("simulation_markers"),
            "simulated": bool(real_result.get("simulated", False)),
        },
        "blockers": job_blockers,
    }
    return {key: output.get(key) for key in OUTPUT_KEYS}


def failed_output(
    job_id: str,
    run_dir: Path,
    attempts: list[dict[str, Any]],
    routing_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": "failed",
        "run_dir": str(run_dir),
        **threshold_fields(routing_decision, None),
        "content_score": None,
        "desk_reject": None,
        "above_5_5": False,
        "gates": {},
        "doi_real_rate": None,
        "pdf_path": None,
        "real_vs_simulated": {"real_status": "failed", "simulated": False},
        "blockers": [f"pipeline failed for all routed models: {attempts}"],
    }


def write_contract_markdown(run_dir: Path, contract: dict[str, Any]) -> None:
    data_source = contract.get("data_source", {})
    text = "\n".join([
        "# Research Contract",
        "",
        f"- Job ID: {contract.get('job_id')}",
        f"- Source: {contract.get('source')}",
        f"- Level: {contract.get('level')}",
        f"- Tier: {contract.get('tier')}",
        f"- Topic: {contract.get('topic')}",
        f"- Research Question: {contract.get('research_question')}",
        f"- Contribution: {contract.get('contribution')}",
        f"- Data Source: {data_source.get('name')} ({data_source.get('type')})",
        f"- Probe Required: {data_source.get('probe_required')}",
        f"- Target Journal: {contract.get('target_journal')}",
        f"- Model Policy: {contract.get('model_policy', 'derived-by-level')}",
        "",
    ])
    (run_dir / "research_contract.md").write_text(text, encoding="utf-8")


def repo_owner_from_contract(contract: dict[str, Any]) -> str | None:
    explicit = str(contract.get("repo_owner") or os.environ.get("PROJECTS_REPO_OWNER") or "").strip()
    if explicit:
        return explicit
    repo = str(os.environ.get("PROJECTS_REPO") or "").strip()
    if "/" in repo:
        return repo.split("/", 1)[0]
    repo_url = str(contract.get("repo_url") or "").strip()
    parsed = urllib.parse.urlparse(repo_url)
    parts = [part for part in parsed.path.split("/") if part]
    return parts[0] if len(parts) >= 2 else None


def repo_name_from_contract(contract: dict[str, Any]) -> str | None:
    explicit = str(contract.get("repo_name") or "").strip()
    if explicit:
        return explicit
    project_id = str(contract.get("project_id") or contract.get("job_id") or "").strip()
    return f"paperlab-{project_id}" if project_id else None


def github_json(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "paper-a-job-service",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"message": raw[:500]}
        return exc.code, body


def ensure_project_repo(contract: dict[str, Any]) -> dict[str, Any]:
    token = os.environ.get("PROJECTS_GITHUB_PAT", "").strip()
    owner = repo_owner_from_contract(contract)
    name = repo_name_from_contract(contract)
    if not token or not owner or not name:
        return {
            "status": "disabled",
            "reason": "PROJECTS_GITHUB_PAT, PROJECTS_REPO/PROJECTS_REPO_OWNER, or project_id is missing",
        }

    repo_api = f"https://api.github.com/repos/{owner}/{name}"
    status_code, body = github_json("GET", repo_api, token)
    if status_code == 200:
        return {"status": "ok", "repo": f"{owner}/{name}", "repo_url": body.get("html_url") or f"https://github.com/{owner}/{name}"}
    if status_code != 404:
        return {"status": "error", "stage": "repo_get", "code": status_code, "message": body.get("message")}

    create_payload = {
        "name": name,
        "private": True,
        "auto_init": False,
        "description": f"Paper Lab pipeline project {contract.get('project_id') or contract.get('job_id')}",
    }
    status_code, body = github_json("POST", f"https://api.github.com/orgs/{owner}/repos", token, create_payload)
    if status_code == 404:
        status_code, body = github_json("POST", "https://api.github.com/user/repos", token, create_payload)
    if status_code not in {200, 201}:
        return {"status": "error", "stage": "repo_create", "code": status_code, "message": body.get("message")}
    return {"status": "ok", "repo": f"{owner}/{name}", "repo_url": body.get("html_url") or f"https://github.com/{owner}/{name}"}


def github_upsert_file(repo_full_name: str, token: str, path: str, content: bytes, message: str) -> dict[str, Any]:
    encoded_path = urllib.parse.quote(path, safe="/")
    api_url = f"https://api.github.com/repos/{repo_full_name}/contents/{encoded_path}"
    sha = None
    status_code, body = github_json("GET", api_url, token)
    if status_code == 200:
        sha = body.get("sha")
    elif status_code != 404:
        return {"status": "error", "path": path, "code": status_code, "message": body.get("message")}
    payload: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content).decode("ascii"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    status_code, body = github_json("PUT", api_url, token, payload)
    if status_code not in {200, 201}:
        return {"status": "error", "path": path, "code": status_code, "message": body.get("message")}
    return {"status": "ok", "path": path, "url": body.get("content", {}).get("html_url")}


def repo_files_for_stage(
    contract: dict[str, Any],
    stage: str,
    job_dir: Path,
    run_dir: Path | None = None,
    output: dict[str, Any] | None = None,
) -> dict[str, bytes]:
    proposal = str(contract.get("proposal_markdown") or "# Proposal\n\nNo proposal markdown was included in the contract.\n")
    readme = "\n".join([
        f"# Paper Lab Project: {contract.get('topic') or contract.get('job_id')}",
        "",
        f"- Project ID: {contract.get('project_id')}",
        f"- Job ID: {contract.get('job_id')}",
        f"- Stage: {stage}",
        f"- Status URL: {contract.get('status_url') or ''}",
        "",
        "This repository is created early by the a-side job service so the b-side predicted URL becomes live before the long pipeline finishes.",
        "",
    ])
    files = {
        "README.md": readme.encode("utf-8"),
        "proposal.md": proposal.encode("utf-8"),
        "research_contract.json": json.dumps(contract, indent=2, ensure_ascii=False).encode("utf-8"),
    }
    if output is not None:
        files["output.json"] = json.dumps(output, indent=2, ensure_ascii=False).encode("utf-8")
        result_md = "\n".join([
            "# Pipeline Result",
            "",
            f"- Status: {output.get('status')}",
            f"- Content score: {output.get('content_score')}",
            f"- Meets threshold: {output.get('meets_threshold')}",
            f"- PDF: {output.get('pdf_path')}",
            "",
            "## Blockers",
            *(f"- {item}" for item in output.get("blockers", []) if item),
            "",
        ])
        files["result.md"] = result_md.encode("utf-8")
        pdf_path = output.get("pdf_path")
        if isinstance(pdf_path, str):
            pdf = Path(pdf_path)
            if pdf.is_file():
                files["paper_draft_v0.pdf"] = pdf.read_bytes()
    if run_dir is not None and (run_dir / "research_contract.md").is_file():
        files["research_contract.md"] = (run_dir / "research_contract.md").read_bytes()
    if (job_dir / "worker.log").is_file():
        files["logs/worker.log"] = (job_dir / "worker.log").read_bytes()
    return files


def sync_project_repo(
    contract: dict[str, Any],
    stage: str,
    job_dir: Path,
    run_dir: Path | None = None,
    output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = ensure_project_repo(contract)
    if repo.get("status") != "ok":
        return repo
    token = os.environ.get("PROJECTS_GITHUB_PAT", "").strip()
    repo_full_name = str(repo["repo"])
    results = []
    for path, content in repo_files_for_stage(contract, stage, job_dir, run_dir, output).items():
        results.append(github_upsert_file(repo_full_name, token, path, content, f"chore: sync {stage} for {contract.get('job_id')}"))
    failed = [item for item in results if item.get("status") != "ok"]
    return {
        "status": "error" if failed else "ok",
        "stage": stage,
        "repo": repo_full_name,
        "repo_url": repo.get("repo_url"),
        "files": results,
    }


def notify_admin(message: str) -> dict[str, Any]:
    """Best-effort Telegram ping to the admin (GPU approvals etc.). Configured via
    PAPER_TG_BOT_TOKEN / PAPER_TG_CHAT_ID env on ac-2012; silent failure never
    blocks the job flow (the blocked state itself is the durable signal)."""
    token = os.environ.get("PAPER_TG_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("PAPER_TG_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"status": "not_configured"}
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("ascii")
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"status": "sent" if resp.status == 200 else f"http_{resp.status}"}
    except Exception as exc:  # noqa: BLE001 - notification must never break the job
        return {"status": "failed", "error": str(exc)[:200]}


def _notify_via_webhook(email: str, subject: str, text: str) -> dict[str, Any] | None:
    """Cloudflare Email Worker path (no SMTP): POST to the paper-notify worker,
    which sends via the send_email binding to the account's verified destination.
    Returns None when not configured so the caller falls through the chain."""
    url = os.environ.get("NOTIFY_WEBHOOK_URL", "").strip()
    token = os.environ.get("NOTIFY_WEBHOOK_TOKEN", "").strip()
    if not url or not token:
        return None
    payload = json.dumps({"to": email, "subject": subject, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(500).decode("utf-8", "ignore")
            return {"status": "sent" if resp.status == 200 else f"http_{resp.status}", "via": "cloudflare_email_worker", "detail": body}
    except Exception as exc:  # noqa: BLE001 - notification must never break the job
        return {"status": "failed", "via": "cloudflare_email_worker", "error": str(exc)[:200]}


def trigger_status_reconcile() -> dict[str, Any]:
    """Best-effort poke of the paperlab-kb worker's status reconciler so the
    /projects/ listing reflects this terminal state within seconds. The D1
    projects.status column froze at 'submitted' for every job before this loop
    existed (2026-07-11: user saw done_pass papers listed as 已送出/執行中);
    the 10-minute paper-status-reconcile.timer on ac-2012 is the backstop when
    this immediate poke fails."""
    url = os.environ.get("RECONCILE_URL", "").strip()
    token = os.environ.get("RECONCILE_TOKEN", "").strip()
    if not url or not token:
        return {"status": "not_configured"}
    req = urllib.request.Request(
        url, data=b"", method="POST", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"status": "ok", "code": resp.status}
    except Exception as exc:  # noqa: BLE001 - reconcile must never break the job
        return {"status": "error", "error": str(exc)[:200]}


def notify_completion(contract: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    # Status writeback fires on EVERY terminal state, before the email
    # short-circuit below — jobs without notify_email still own a listing row.
    trigger_status_reconcile()
    email = str(contract.get("notify_email") or "").strip()
    if not email:
        return {"status": "skipped", "reason": "notify_email not provided"}
    subject = f"Paper Lab job {output.get('status')}: {contract.get('topic') or contract.get('job_id')}"
    text = "\n".join([
        f"Job ID: {contract.get('job_id')}",
        f"Status: {output.get('status')}",
        f"Result: {contract.get('status_url') or 'https://paperlab.cooperation.tw/projects/'}",
        "",
        f"Blockers: {', '.join(output.get('blockers', [])) if output.get('blockers') else 'none'}",
    ])
    # Chain: Cloudflare Email Worker -> SMTP (if ever configured) -> Telegram.
    webhook = _notify_via_webhook(email, subject, text)
    if webhook is not None and webhook.get("status") == "sent":
        return {"status": "sent", "email": email, "via": "cloudflare_email_worker"}
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    if not smtp_host:
        # ⚠️ 沉默失敗=設計缺陷 (2026-07-10): SMTP was never configured on ac-2012,
        # so every completion notice silently returned not_configured while the
        # submission flow PROMISED the user an email — the first fresh E2E user
        # asked "我沒收到信件". Fall back to the Telegram admin channel (which IS
        # configured and is the operator's documented alert path) so a terminal
        # state always produces a real notification somewhere visible.
        tg = notify_admin(
            "Paper Lab job %s: %s\nJob: %s\nnotify_email (SMTP unconfigured, TG fallback): %s\nBlockers: %s"
            % (
                output.get("status"),
                str(contract.get("topic") or "")[:80],
                contract.get("job_id"),
                email,
                ", ".join(output.get("blockers", [])) if output.get("blockers") else "none",
            )
        )
        return {
            "status": "telegram_fallback",
            "email": email,
            "telegram": tg,
            "todo": "Set SMTP_HOST/SMTP_PORT/SMTP_USERNAME/SMTP_PASSWORD/SMTP_FROM on ac-2012 for real email delivery.",
        }
    msg = EmailMessage()
    sender = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USERNAME", "paper-a@localhost"))
    msg["From"] = sender
    msg["To"] = email
    msg["Subject"] = f"Paper Lab job {output.get('status')}: {contract.get('topic') or contract.get('job_id')}"
    msg.set_content(
        "\n".join([
            f"Job ID: {contract.get('job_id')}",
            f"Status: {output.get('status')}",
            f"Repo: {contract.get('repo_url') or ''}",
            f"Result: {contract.get('status_url') or ''}",
            "",
            f"Blockers: {', '.join(output.get('blockers', [])) if output.get('blockers') else 'none'}",
        ]),
    )
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    try:
        with smtplib.SMTP(smtp_host, port, timeout=20) as smtp:
            if os.environ.get("SMTP_STARTTLS", "true").lower() not in {"0", "false", "no"}:
                smtp.starttls()
            if username:
                smtp.login(username, password)
            smtp.send_message(msg)
        return {"status": "sent", "email": email}
    except Exception as exc:
        return {"status": "failed", "email": email, "error": str(exc)}


def run_job(job_id: str, jobs_dir: Path = DEFAULT_JOBS_DIR) -> dict[str, Any]:
    job_dir = job_dir_for(job_id, jobs_dir)
    contract = read_json(job_dir / "contract.json")
    routing_decision = read_json(job_dir / "routing_decision.json")
    if not isinstance(contract, dict) or not isinstance(routing_decision, dict):
        raise FileNotFoundError(f"missing job contract or route for {job_id}")
    run_dir = job_dir / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "research_contract.json", contract)
    write_contract_markdown(run_dir, contract)
    update_state(job_dir, "running", "worker started", run_dir=str(run_dir), routing_decision=routing_decision)

    # GPU lane never auto-runs (tier policy): park the job, tell the member to
    # expect contact, and notify the admin. Manual approval restarts it later.
    if routing_decision.get("needs_manual_approval"):
        reason = ("GPU lane requires manual approval — the job is parked, not running. "
                  "Paper Lab will contact you to schedule the GPU run.")
        output = {
            "job_id": job_id, "status": "blocked", "run_dir": str(run_dir),
            "gates": {"manual_approval": {"status": "pending", "reason": reason}},
            "content_score": None, "meets_threshold": False, "pdf_path": None,
            "real_vs_simulated": {"real_status": "not_run", "simulated": False},
            "blockers": [reason],
        }
        write_json(job_dir / "output.json", output)
        notification = notify_completion(contract, output)
        notify_admin(f"GPU approval needed: job {job_id} "
                     f"(topic: {str(contract.get('topic'))[:80]}, tier: {contract.get('tier')})")
        update_state(job_dir, "blocked", reason, output=output, notification=notification)
        return output

    repo_sync = sync_project_repo(contract, "skeleton", job_dir, run_dir)
    update_state(job_dir, "running", "repo skeleton sync attempted", repo_sync=repo_sync)

    lock = probe_data_source(contract, run_dir)
    if lock.get("status") != "available":
        output = blocked_output(job_id, run_dir, lock, routing_decision)
        write_json(job_dir / "output.json", output)
        repo_sync = sync_project_repo(contract, "blocked", job_dir, run_dir, output)
        notification = notify_completion(contract, output)
        update_state(job_dir, "blocked", str(output["blockers"][0]), output=output, repo_sync=repo_sync, notification=notification)
        return output
    update_state(job_dir, "running", "data gate passed", data_source_lock=lock)

    attempts = run_pipeline(job_dir, run_dir, routing_decision)
    last_rc = attempts[-1].get("returncode") if attempts else 1
    if last_rc == BLOCKED_EXIT:
        # Deterministic block (non-viable plan / data): a clean "blocked", not a
        # retried "failed". Surface the real reason from the blocked real_results.
        rr = read_json(run_dir / "real_experiments" / "real_results.json")
        reason = (rr.get("reason") if isinstance(rr, dict) else None) \
            or "plan/data not viable (phase-0 or lane block)"
        output = failed_output(job_id, run_dir, attempts, routing_decision)
        output["status"] = "blocked"
        output["blockers"] = [reason]
        write_json(job_dir / "output.json", output)
        repo_sync = sync_project_repo(contract, "blocked", job_dir, run_dir, output)
        notification = notify_completion(contract, output)
        update_state(job_dir, "blocked", f"blocked: {reason[:90]}", attempts=attempts,
                     output=output, repo_sync=repo_sync, notification=notification)
        return output
    success = last_rc == 0
    if not success:
        output = failed_output(job_id, run_dir, attempts, routing_decision)
        write_json(job_dir / "output.json", output)
        repo_sync = sync_project_repo(contract, "failed", job_dir, run_dir, output)
        notification = notify_completion(contract, output)
        update_state(job_dir, "failed", "pipeline failed", attempts=attempts, output=output, repo_sync=repo_sync, notification=notification)
        return output

    output = extract_output(job_id, run_dir, [], routing_decision)
    write_json(job_dir / "output.json", output)
    repo_sync = sync_project_repo(contract, str(output["status"]), job_dir, run_dir, output)
    notification = notify_completion(contract, output)
    update_state(job_dir, output["status"], "pipeline completed", attempts=attempts, output=output, repo_sync=repo_sync, notification=notification)
    return output


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    submit_ap = sub.add_parser("submit")
    submit_ap.add_argument("contract")
    submit_ap.add_argument("--jobs-dir", default=str(DEFAULT_JOBS_DIR))
    submit_ap.add_argument("--no-start", action="store_true")
    status_ap = sub.add_parser("status")
    status_ap.add_argument("job_id")
    status_ap.add_argument("--jobs-dir", default=str(DEFAULT_JOBS_DIR))
    result_ap = sub.add_parser("result")
    result_ap.add_argument("job_id")
    result_ap.add_argument("--jobs-dir", default=str(DEFAULT_JOBS_DIR))
    worker_ap = sub.add_parser("worker")
    worker_ap.add_argument("--job-id", required=True)
    worker_ap.add_argument("--jobs-dir", default=str(DEFAULT_JOBS_DIR))
    route_ap = sub.add_parser("route")
    route_ap.add_argument("contract")

    args = ap.parse_args(argv)
    if args.cmd == "submit":
        print_json(submit(Path(args.contract), Path(args.jobs_dir), start_worker=not args.no_start))
        return 0
    if args.cmd == "status":
        print_json(status(args.job_id, Path(args.jobs_dir)))
        return 0
    if args.cmd == "result":
        print_json(result(args.job_id, Path(args.jobs_dir)))
        return 0
    if args.cmd == "worker":
        output = run_job(args.job_id, Path(args.jobs_dir))
        print_json(output)
        return 0 if output.get("status") in {"done", "blocked"} else 2
    if args.cmd == "route":
        print_json(router.route_contract(load_contract(Path(args.contract))))
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
