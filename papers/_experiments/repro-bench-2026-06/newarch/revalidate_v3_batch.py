from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from batch_validate_v3 import JobValidation, decide_batch_gate, validate_jobs
from engine_v3.core import DossierStore
from engine_v3.core.orchestrator import EngineV3Orchestrator
from engine_v3.packs.paper import PaperPack
from engine_v3.pipelines.paper import full_paper_pipeline
from engine_v3.runtime_config import (
    HERMES_OUTPUT_COMPLETE_GRACE_ENV,
    HERMES_OUTPUT_PARTIAL_IDLE_ENV,
    HERMES_OUTPUT_STARTUP_IDLE_ENV,
    HERMES_TIMEOUT_ENV,
    runtime_from_env,
)


@dataclass(frozen=True)
class RunOutcome:
    job_id: str
    status: str
    phases: dict[str, str]
    seconds: float
    has_pdf: bool
    error: str | None


@dataclass(frozen=True)
class RevalidationRow:
    run: RunOutcome
    validation: JobValidation


RunOne = Callable[[Path, str], RunOutcome]
Validate = Callable[..., list[JobValidation]]


def main() -> int:
    parser = argparse.ArgumentParser(description="Sequentially revalidate Paper Lab V3 jobs with bounded runtime settings.")
    parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    parser.add_argument("--job-id", action="append", default=[], required=True)
    parser.add_argument("--min-floor", type=float, default=80.0)
    parser.add_argument("--runtime-timeout-s", type=int, default=None)
    parser.add_argument("--startup-idle-s", type=float, default=None)
    parser.add_argument("--partial-idle-s", type=float, default=None)
    parser.add_argument("--complete-grace-s", type=float, default=None)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--batch-gate", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    _apply_runtime_bounds(args)
    rows = revalidate_jobs(args.jobs_dir, args.job_id, min_floor=args.min_floor)
    if args.json_output:
        print(json.dumps([_row_dict(row) for row in rows], ensure_ascii=False, indent=2))
    else:
        _print_table(rows)
    decision = decide_batch_gate([row.validation for row in rows])
    if args.batch_gate:
        print(json.dumps(asdict(decision), ensure_ascii=False, indent=2))
    if (args.strict and any(not row.validation.passed for row in rows)) or (args.batch_gate and not decision.passed):
        return 1
    return 0


def revalidate_jobs(
    jobs_dir: Path,
    job_ids: list[str],
    *,
    min_floor: float = 80.0,
    run_one: RunOne | None = None,
    validate: Validate = validate_jobs,
) -> list[RevalidationRow]:
    jobs_dir = jobs_dir.expanduser()
    runner = run_one or _run_one_orchestrator
    rows: list[RevalidationRow] = []
    for job_id in job_ids:
        print("REVALIDATE_START\t%s" % job_id, flush=True)
        try:
            if run_one is None:
                preflight = validate(jobs_dir, job_ids=[job_id], min_floor=min_floor)[0]
                _prepare_acceptance_repair_resume(jobs_dir, job_id, preflight)
                _prepare_review_provenance_resume(jobs_dir, job_id)
            outcome = runner(jobs_dir, job_id)
        except Exception as exc:  # noqa: BLE001 - batch runners must keep going.
            outcome = RunOutcome(
                job_id=job_id,
                status="exception",
                phases={},
                seconds=0.0,
                has_pdf=False,
                error="%s: %s\n%s" % (type(exc).__name__, exc, traceback.format_exc(limit=5)),
            )
        validation = validate(jobs_dir, job_ids=[job_id], min_floor=min_floor)[0]
        row = RevalidationRow(run=outcome, validation=validation)
        rows.append(row)
        print("REVALIDATE_RESULT\t%s" % json.dumps(_row_dict(row), ensure_ascii=False), flush=True)
    return rows


def _prepare_acceptance_repair_resume(jobs_dir: Path, job_id: str, validation: JobValidation) -> bool:
    if validation.passed:
        return False
    if not _delivery_repairable_acceptance_failure(validation):
        return False
    dossier_path = jobs_dir / job_id / "run" / "dossier.v3.json"
    try:
        dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    phases = dossier.get("phases")
    if not isinstance(phases, dict):
        return False
    if phases.get("format_repair") != "done":
        return False
    phases["format_repair"] = "blocked"
    dossier_path.write_text(json.dumps(dossier, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return True


def _prepare_review_provenance_resume(jobs_dir: Path, job_id: str) -> bool:
    """Reset the quality phases when the recorded review has no trustworthy
    provenance, so orchestrator resume re-runs them instead of skipping.

    Ground-truth based: it consumes review_provenance.validate_review_artifacts
    on the run directory (the same rules as Gate R), not string-matched
    validation findings, so any provenance failure class routes here without
    enumerating messages. Data/write phases stay done; only the quality
    machinery (render_gates, review_heal, format_repair) re-runs.
    """
    from engine_v3 import review_provenance
    from engine_v3.packs import paper_artifacts

    run_dir = jobs_dir / job_id / "run"
    findings = review_provenance.validate_review_artifacts(
        run_dir,
        review_file=paper_artifacts.REVIEW_FILE,
        review_log_file=paper_artifacts.REVIEW_LOG_FILE,
        manuscript_files=paper_artifacts.MANUSCRIPT_FILES,
    )
    if not findings:
        return False
    dossier_path = run_dir / "dossier.v3.json"
    try:
        dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    phases = dossier.get("phases")
    if not isinstance(phases, dict):
        return False
    changed = False
    for phase in ("render_gates", "review_heal", "format_repair"):
        if phases.get(phase) == "done":
            phases[phase] = "blocked"
            changed = True
    # Grant the reset phases a fresh repair budget: prior attempts belong to
    # the superseded (provenance-invalid) run. The delegation audit trail is
    # untouched; the orchestrator subtracts this baseline when counting the
    # budget. Also applies when an earlier reset already left phases blocked.
    evidence = dossier.setdefault("evidence", {})
    baselines = evidence.setdefault("repair_budget_baseline", {})
    delegations = dossier.get("delegations") or []
    for phase in ("render_gates", "review_heal", "format_repair"):
        if phases.get(phase) != "blocked":
            continue
        prefix = "%s:repair:" % phase
        attempts = [
            int(str(d.get("task_id") or "").rsplit(":", 1)[-1])
            for d in delegations
            if str(d.get("task_id") or "").startswith(prefix)
            and str(d.get("task_id") or "").rsplit(":", 1)[-1].isdigit()
        ]
        baseline = max(attempts, default=0)
        if baselines.get(phase) != baseline:
            baselines[phase] = baseline
            changed = True
    if not changed:
        return False
    dossier_path.write_text(json.dumps(dossier, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print("REVALIDATE_PROVENANCE_RESET	%s	%s" % (job_id, "; ".join(findings[:3])), flush=True)
    return True


def _delivery_repairable_acceptance_failure(validation: JobValidation) -> bool:
    findings = " | ".join(validation.findings)
    return validation.status == "done" and any(
        marker in findings
        for marker in (
            "PDF content-quality validation missing",
            "PDF contains repeated fallback boilerplate",
            "PDF contains low-quality citation labels",
            "PDF contains duplicated traceability addenda or tables",
            "Z gate delivery PDF validation missing",
        )
    )


def _run_one_orchestrator(jobs_dir: Path, job_id: str) -> RunOutcome:
    started = time.monotonic()
    run_dir = jobs_dir / job_id / "run"
    dossier = EngineV3Orchestrator(
        runtime=runtime_from_env(),
        domain_pack=PaperPack(),
        phases=full_paper_pipeline(),
        dossier_store=DossierStore(run_dir),
    ).run(job_id=job_id, resume=True)
    phases = dict(dossier.phases)
    return RunOutcome(
        job_id=job_id,
        status=_status(phases),
        phases=phases,
        seconds=round(time.monotonic() - started, 1),
        has_pdf=(run_dir / "paper_draft_v0.pdf").is_file(),
        error=None,
    )


def _status(phases: dict[str, str]) -> str:
    if any(status == "error" for status in phases.values()):
        return "failed"
    if any(status == "blocked" for status in phases.values()):
        return "blocked"
    if phases.get("format_repair") == "done":
        return "done"
    return "partial" if phases else "missing"


def _apply_runtime_bounds(args: argparse.Namespace) -> None:
    _set_env_if_present(HERMES_TIMEOUT_ENV, args.runtime_timeout_s)
    _set_env_if_present(HERMES_OUTPUT_STARTUP_IDLE_ENV, args.startup_idle_s)
    _set_env_if_present(HERMES_OUTPUT_PARTIAL_IDLE_ENV, args.partial_idle_s)
    _set_env_if_present(HERMES_OUTPUT_COMPLETE_GRACE_ENV, args.complete_grace_s)


def _set_env_if_present(name: str, value: Any) -> None:
    if value is not None:
        os.environ[name] = str(value)


def _row_dict(row: RevalidationRow) -> dict[str, Any]:
    return {
        "run": asdict(row.run),
        "validation": asdict(row.validation),
    }


def _print_table(rows: list[RevalidationRow]) -> None:
    print("job_id\trun_status\tacceptance\tpassed\tseconds\tfloor_100\tdelivery\tfindings")
    for row in rows:
        validation = row.validation
        print(
            "%s\t%s\t%s\t%s\t%.1f\t%s\t%s\t%s"
            % (
                row.run.job_id,
                row.run.status,
                validation.acceptance_status,
                "yes" if validation.passed else "no",
                row.run.seconds,
                "" if validation.floor_100 is None else "%.1f" % validation.floor_100,
                validation.delivery,
                " | ".join(validation.findings),
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
