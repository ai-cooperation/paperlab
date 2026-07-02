from __future__ import annotations

from pathlib import Path

import pytest

from batch_validate_v3 import JobValidation
from revalidate_v3_batch import RunOutcome, _prepare_acceptance_repair_resume, revalidate_jobs

pytestmark = pytest.mark.unit


def test_revalidate_jobs_continues_after_one_job_errors(tmp_path: Path):
    calls: list[str] = []

    def fake_run_one(jobs_dir: Path, job_id: str) -> RunOutcome:
        calls.append(job_id)
        if job_id == "v3_bad":
            raise RuntimeError("boom")
        return RunOutcome(
            job_id=job_id,
            status="done",
            phases={"format_repair": "done"},
            seconds=1.2,
            has_pdf=True,
            error=None,
        )

    def fake_validate(_jobs_dir: Path, *, job_ids: list[str], min_floor: float = 80.0):
        job_id = job_ids[0]
        return [
            JobValidation(
                job_id=job_id,
                status="done" if job_id == "v3_good" else "partial",
                passed=job_id == "v3_good",
                phases_done=job_id == "v3_good",
                gates_done=job_id == "v3_good",
                review_ok=job_id == "v3_good",
                pdf_ok=job_id == "v3_good",
                acceptance_ok=job_id == "v3_good",
                acceptance_status="done_pass" if job_id == "v3_good" else "failed_repairable",
                floor_100=82.0 if job_id == "v3_good" else None,
                delivery="pass" if job_id == "v3_good" else "",
                findings=[] if job_id == "v3_good" else ["failed"],
            )
        ]

    rows = revalidate_jobs(
        tmp_path,
        ["v3_bad", "v3_good"],
        run_one=fake_run_one,
        validate=fake_validate,
    )

    assert calls == ["v3_bad", "v3_good"]
    assert rows[0].run.status == "exception"
    assert rows[0].validation.passed is False
    assert rows[1].run.status == "done"
    assert rows[1].validation.passed is True


def test_prepare_acceptance_repair_resume_marks_format_repair_for_rerun(tmp_path: Path):
    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "dossier.v3.json").write_text(
        '{"phases":{"data":"done","format_repair":"done"}}',
        encoding="utf-8",
    )
    validation = JobValidation(
        job_id="v3_job",
        status="done",
        passed=False,
        phases_done=True,
        gates_done=True,
        review_ok=True,
        pdf_ok=False,
        acceptance_ok=False,
        acceptance_status="failed_needs_human",
        floor_100=82.0,
        delivery="pass",
        findings=["PDF content-quality validation missing"],
    )

    changed = _prepare_acceptance_repair_resume(tmp_path, "v3_job", validation)

    assert changed is True
    assert '"format_repair": "blocked"' in (run_dir / "dossier.v3.json").read_text(encoding="utf-8")
