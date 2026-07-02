from __future__ import annotations

import json
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


def test_revalidation_resets_quality_phases_when_review_provenance_invalid(tmp_path: Path):
    from revalidate_v3_batch import _prepare_review_provenance_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "dossier.v3.json").write_text(
        '{"phases":{"data":"done","write":"done","render_gates":"done",'
        '"review_heal":"done","format_repair":"done"}}',
        encoding="utf-8",
    )
    # The 2026-07-02 Potemkin shape: synthesized deterministic pass review,
    # no review_method, no decision trace.
    (run_dir / "quality_review_round1.json").write_text(
        '{"p0_count":0,"delivery":"pass","floor_100":82.0,'
        '"review_loop":{"status":"passed","rounds":1,'
        '"reviewer_model":"deterministic bounded final review",'
        '"fixer_model":"deterministic structural repair",'
        '"independent_reviewer":true,"floor_failed":false}}',
        encoding="utf-8",
    )
    (run_dir / "quality_review_log.md").write_text("Reviewer: deterministic.\n", encoding="utf-8")

    changed = _prepare_review_provenance_resume(tmp_path, "v3_job")

    assert changed is True
    dossier = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert dossier["phases"]["render_gates"] == "blocked"
    assert dossier["phases"]["review_heal"] == "blocked"
    assert dossier["phases"]["format_repair"] == "blocked"
    assert dossier["phases"]["data"] == "done"
    assert dossier["phases"]["write"] == "done"


def test_revalidation_leaves_phases_alone_when_review_provenance_valid(tmp_path: Path):
    from engine_v3 import review_provenance
    from revalidate_v3_batch import _prepare_review_provenance_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "paper_draft_v0.qmd").write_text("reviewed content", encoding="utf-8")
    stamp = review_provenance.manuscript_sha256(run_dir, ("paper_draft_v0.qmd",))
    (run_dir / "dossier.v3.json").write_text(
        '{"phases":{"review_heal":"done","format_repair":"done"}}',
        encoding="utf-8",
    )
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps(
            {
                "p0_count": 0,
                "delivery": "pass",
                "floor_100": 84,
                "review_method": {
                    "schema_version": "paperlab.review_method.v3.2",
                    "decision_owner": "hermes",
                    "capability_class": "domain_expert_review",
                    "selected_skill": "paper-review-skill",
                    "selection_reason": "domain expert review",
                    "vip_capability_required": True,
                    "vip_capability_available": True,
                    "inputs_checked": ["paper_draft_v0.qmd"],
                    "reviewed_manuscript_sha256": stamp,
                },
                "review_loop": {
                    "status": "passed",
                    "rounds": 1,
                    "reviewer_model": "codex-reviewer",
                    "fixer_model": "big-pickle",
                    "independent_reviewer": True,
                    "floor_failed": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "quality_review_log.md").write_text(
        "# log\n\n## Skill Decision Trace\n\n- selected: paper-review-skill\n",
        encoding="utf-8",
    )

    changed = _prepare_review_provenance_resume(tmp_path, "v3_job")

    assert changed is False
    dossier = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert dossier["phases"]["review_heal"] == "done"
