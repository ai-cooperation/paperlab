from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REQUIRED_PHASES = {
    "data",
    "gap",
    "structure",
    "write",
    "claim_evidence",
    "render_gates",
    "review_heal",
    "format_repair",
}
REQUIRED_REVIEW_DIMENSIONS = {
    "academic_rigor",
    "novelty_positioning",
    "experimental_completeness",
    "writing_quality",
    "practical_feasibility",
    "citation_accuracy",
    "format_compliance",
}


@dataclass(frozen=True)
class JobValidation:
    job_id: str
    status: str
    passed: bool
    phases_done: bool
    gates_done: bool
    review_ok: bool
    pdf_ok: bool
    floor_100: float | None
    delivery: str
    findings: list[str]


@dataclass(frozen=True)
class BatchGateDecision:
    passed: bool
    total: int
    failed: int
    blocked: int
    reason: str


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Paper Lab engine v3 job outputs.")
    parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    parser.add_argument("--job-id", action="append", default=[])
    parser.add_argument("--min-floor", type=float, default=80.0)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--batch-gate", action="store_true", help="Print and enforce batch-level stop decision.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any selected job fails.")
    args = parser.parse_args()

    rows = validate_jobs(args.jobs_dir, job_ids=args.job_id, min_floor=args.min_floor)
    decision = decide_batch_gate(rows)
    if args.json_output:
        print(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2))
    else:
        _print_table(rows)
    if args.batch_gate:
        print(json.dumps(asdict(decision), ensure_ascii=False, indent=2))
    if (args.strict and any(not row.passed for row in rows)) or (args.batch_gate and not decision.passed):
        return 1
    return 0


def validate_jobs(
    jobs_dir: Path,
    *,
    job_ids: list[str] | None = None,
    min_floor: float = 80.0,
) -> list[JobValidation]:
    jobs_dir = jobs_dir.expanduser()
    selected = job_ids or [path.name for path in sorted(jobs_dir.glob("v3_*")) if path.is_dir()]
    return [_validate_job(jobs_dir, job_id, min_floor=min_floor) for job_id in selected]


def decide_batch_gate(rows: list[JobValidation]) -> BatchGateDecision:
    blocked = sum(1 for row in rows if row.status == "blocked")
    failed = sum(1 for row in rows if not row.passed)
    if not rows:
        return BatchGateDecision(
            passed=False,
            total=0,
            failed=0,
            blocked=0,
            reason="no jobs selected",
        )
    if blocked:
        return BatchGateDecision(
            passed=False,
            total=len(rows),
            failed=failed,
            blocked=blocked,
            reason="stop batch: blocked jobs present",
        )
    if failed:
        return BatchGateDecision(
            passed=False,
            total=len(rows),
            failed=failed,
            blocked=blocked,
            reason="stop batch: failed validation jobs present",
        )
    return BatchGateDecision(
        passed=True,
        total=len(rows),
        failed=0,
        blocked=0,
        reason="batch passed",
    )


def _validate_job(jobs_dir: Path, job_id: str, *, min_floor: float) -> JobValidation:
    run_dir = jobs_dir / job_id / "run"
    findings: list[str] = []
    dossier = _read_json(run_dir / "dossier.v3.json")
    if not isinstance(dossier, dict):
        return JobValidation(
            job_id=job_id,
            status="missing_dossier",
            passed=False,
            phases_done=False,
            gates_done=False,
            review_ok=False,
            pdf_ok=False,
            floor_100=None,
            delivery="",
            findings=["missing or invalid dossier.v3.json"],
        )

    phases = dossier.get("phases") if isinstance(dossier.get("phases"), dict) else {}
    phases_done = REQUIRED_PHASES.issubset(phases) and all(phases.get(phase) == "done" for phase in REQUIRED_PHASES)
    if not phases_done:
        missing = sorted(REQUIRED_PHASES - set(phases))
        blocked = sorted(phase for phase in REQUIRED_PHASES if phases.get(phase) != "done")
        if missing:
            findings.append("missing phases: %s" % ", ".join(missing))
        if blocked:
            findings.append("non-done phases: %s" % ", ".join("%s=%s" % (p, phases.get(p)) for p in blocked))

    latest_gate_by_phase = _latest_gate_reports_by_phase(dossier)
    gates_done = True
    for phase in ("claim_evidence", "render_gates", "review_heal", "format_repair"):
        report = latest_gate_by_phase.get(phase)
        if not report:
            gates_done = False
            findings.append("missing latest gate report for %s" % phase)
            continue
        if report.get("blocked"):
            gates_done = False
            findings.append("latest gate report blocked for %s: %s" % (phase, report.get("failed_blocks")))

    review_ok, floor_100, delivery, review_findings = _validate_review(run_dir, min_floor=min_floor)
    findings.extend(review_findings)
    pdf_ok, pdf_findings = _validate_pdf(run_dir, dossier)
    findings.extend(pdf_findings)

    status = "done" if phases_done else ("blocked" if any(value == "blocked" for value in phases.values()) else "partial")
    passed = phases_done and gates_done and review_ok and pdf_ok
    return JobValidation(
        job_id=job_id,
        status=status,
        passed=passed,
        phases_done=phases_done,
        gates_done=gates_done,
        review_ok=review_ok,
        pdf_ok=pdf_ok,
        floor_100=floor_100,
        delivery=delivery,
        findings=findings,
    )


def _validate_review(run_dir: Path, *, min_floor: float) -> tuple[bool, float | None, str, list[str]]:
    findings: list[str] = []
    review = _read_json(run_dir / "quality_review_round1.json")
    if not isinstance(review, dict):
        return False, None, "", ["missing or invalid quality_review_round1.json"]

    delivery = str(review.get("delivery") or "").lower()
    floor = review.get("floor_100")
    floor_100 = float(floor) if isinstance(floor, (int, float)) else None
    if delivery not in {"pass", "passed", "ok"}:
        findings.append("review delivery is not pass: %s" % (delivery or None))
    if floor_100 is None or floor_100 < min_floor:
        findings.append("review floor_100 below %.1f: %s" % (min_floor, floor))
    if int(review.get("p0_count") or 0) != 0:
        findings.append("review p0_count is not zero")

    loop = review.get("review_loop") if isinstance(review.get("review_loop"), dict) else {}
    reviewer_model = str(loop.get("reviewer_model") or "")
    if "fallback" in reviewer_model.lower():
        findings.append("reviewer_model is fallback: %s" % reviewer_model)
    if loop.get("independent_reviewer") is not True:
        findings.append("review_loop.independent_reviewer must be boolean true")
    if str(loop.get("status") or "").lower() not in {"pass", "passed", "ok", "done"}:
        findings.append("review_loop.status is not pass-like: %s" % loop.get("status"))

    dimensions = review.get("dimensions") if isinstance(review.get("dimensions"), dict) else {}
    missing_dimensions = sorted(REQUIRED_REVIEW_DIMENSIONS - set(dimensions))
    if missing_dimensions:
        findings.append("missing review dimensions: %s" % ", ".join(missing_dimensions))
    for key in sorted(REQUIRED_REVIEW_DIMENSIONS & set(dimensions)):
        value = dimensions.get(key)
        score = value.get("score") if isinstance(value, dict) else value
        if not isinstance(score, (int, float)):
            findings.append("dimension score is not numeric: %s" % key)

    log = run_dir / "quality_review_log.md"
    if not log.is_file() or log.stat().st_size < 500:
        findings.append("quality_review_log.md missing or too small")
    return not findings, floor_100, delivery, findings


def _validate_pdf(run_dir: Path, dossier: dict[str, Any]) -> tuple[bool, list[str]]:
    findings: list[str] = []
    pdf = run_dir / "paper_draft_v0.pdf"
    artifacts = dossier.get("artifacts") if isinstance(dossier.get("artifacts"), dict) else {}
    if "paper_draft_v0.pdf" not in artifacts:
        findings.append("paper_draft_v0.pdf missing from artifact index")
    if not pdf.is_file():
        findings.append("paper_draft_v0.pdf missing")
    elif pdf.stat().st_size < 100_000:
        findings.append("paper_draft_v0.pdf too small: %s" % pdf.stat().st_size)
    return not findings, findings


def _latest_gate_reports_by_phase(dossier: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    reports = dossier.get("gate_reports")
    if not isinstance(reports, list):
        return latest
    for report in reports:
        if isinstance(report, dict) and isinstance(report.get("phase"), str):
            latest[report["phase"]] = report
    return latest


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _print_table(rows: list[JobValidation]) -> None:
    print("job_id\tstatus\tpassed\tfloor_100\tdelivery\tfindings")
    for row in rows:
        print(
            "%s\t%s\t%s\t%s\t%s\t%s"
            % (
                row.job_id,
                row.status,
                "yes" if row.passed else "no",
                "" if row.floor_100 is None else "%.1f" % row.floor_100,
                row.delivery,
                " | ".join(row.findings),
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
