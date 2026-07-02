from __future__ import annotations

import json
from pathlib import Path

import pytest

from acceptance_gate_v3 import write_artifact_manifest
from batch_validate_v3 import JobValidation, decide_batch_gate, validate_jobs

pytestmark = pytest.mark.unit


def _row(job_id: str, *, status: str = "done", passed: bool = True) -> JobValidation:
    return JobValidation(
        job_id=job_id,
        status=status,
        passed=passed,
        phases_done=passed,
        gates_done=passed,
        review_ok=passed,
        pdf_ok=passed,
        acceptance_ok=passed,
        acceptance_status="done_pass" if passed else "failed_repairable",
        floor_100=82.0 if passed else None,
        delivery="pass" if passed else "",
        findings=[] if passed else ["failed"],
    )


def test_decide_batch_gate_stops_on_blocked_job():
    decision = decide_batch_gate([_row("v3_a"), _row("v3_b", status="blocked", passed=False)])

    assert decision.passed is False
    assert decision.blocked == 1
    assert decision.failed == 1
    assert "blocked jobs" in decision.reason


def test_decide_batch_gate_passes_all_valid_jobs():
    decision = decide_batch_gate([_row("v3_a"), _row("v3_b")])

    assert decision.passed is True
    assert decision.total == 2
    assert decision.reason == "batch passed"


def test_validate_job_rejects_done_flow_without_acceptance_pdf_contract(tmp_path: Path):
    run_dir = tmp_path / "jobs" / "v3_bad" / "run"
    run_dir.mkdir(parents=True)
    _write_dossier(run_dir, z_validation={"valid": True})
    _write_review(run_dir)
    (run_dir / "quality_review_log.md").write_text("# log\n\n## Skill Decision Trace\n\n- selected: paper-review-skill\n\n" + "reviewed\n" * 100, encoding="utf-8")
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 120_000)

    row = validate_jobs(tmp_path / "jobs", job_ids=["v3_bad"])[0]

    assert row.passed is False
    assert row.acceptance_status == "failed_repairable"
    assert any("artifact_manifest.json missing" in finding for finding in row.findings)


def test_validate_job_requires_z_gate_pdf_validation_details(tmp_path: Path):
    run_dir = tmp_path / "jobs" / "v3_raw_cite" / "run"
    run_dir.mkdir(parents=True)
    _write_manifest(run_dir)
    _write_dossier(
        run_dir,
        z_validation={
            "valid": False,
            "raw_citation_count": 1,
            "unresolved_marker_count": 0,
            "numbered_section_detected": True,
            "table_widths": {"valid": True, "findings": []},
            "findings": ["PDF contains raw Pandoc citation tokens"],
        },
    )
    _write_review(run_dir)
    (run_dir / "quality_review_log.md").write_text("# log\n\n## Skill Decision Trace\n\n- selected: paper-review-skill\n\n" + "reviewed\n" * 100, encoding="utf-8")
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 120_000)

    row = validate_jobs(tmp_path / "jobs", job_ids=["v3_raw_cite"])[0]

    assert row.passed is False
    assert row.pdf_ok is False
    assert row.acceptance_status == "failed_repairable"
    assert "PDF contains raw Pandoc citation tokens" in " | ".join(row.findings)


def test_validate_job_requires_content_quality_validation_in_z_gate(tmp_path: Path):
    run_dir = tmp_path / "jobs" / "v3_missing_content_quality" / "run"
    run_dir.mkdir(parents=True)
    _write_manifest(run_dir)
    validation = dict(_valid_pdf_validation())
    validation.pop("content_quality")
    _write_dossier(run_dir, z_validation=validation)
    _write_review(run_dir)
    (run_dir / "quality_review_log.md").write_text("# log\n\n## Skill Decision Trace\n\n- selected: paper-review-skill\n\n" + "reviewed\n" * 100, encoding="utf-8")
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 120_000)

    row = validate_jobs(tmp_path / "jobs", job_ids=["v3_missing_content_quality"])[0]

    assert row.passed is False
    assert row.acceptance_status == "failed_repairable"
    assert "PDF content-quality validation missing" in " | ".join(row.findings)


def test_validate_job_marks_done_pass_only_for_full_acceptance_contract(tmp_path: Path):
    run_dir = tmp_path / "jobs" / "v3_good" / "run"
    run_dir.mkdir(parents=True)
    _write_manifest(run_dir)
    _write_dossier(run_dir, z_validation=_valid_pdf_validation())
    _write_review(run_dir)
    (run_dir / "quality_review_log.md").write_text("# log\n\n## Skill Decision Trace\n\n- selected: paper-review-skill\n\n" + "reviewed\n" * 100, encoding="utf-8")
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 120_000)

    row = validate_jobs(tmp_path / "jobs", job_ids=["v3_good"])[0]

    assert row.passed is True
    assert row.acceptance_status == "done_pass"
    assert row.acceptance_ok is True
    assert row.findings == []


def test_validate_job_accepts_compact_pdf_when_z_gate_validates_delivery(tmp_path: Path):
    run_dir = tmp_path / "jobs" / "v3_compact_pdf" / "run"
    run_dir.mkdir(parents=True)
    _write_manifest(run_dir)
    _write_dossier(run_dir, z_validation={**_valid_pdf_validation(), "size": 77_138})
    _write_review(run_dir)
    (run_dir / "quality_review_log.md").write_text("# log\n\n## Skill Decision Trace\n\n- selected: paper-review-skill\n\n" + "reviewed\n" * 100, encoding="utf-8")
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 77_000)

    row = validate_jobs(tmp_path / "jobs", job_ids=["v3_compact_pdf"])[0]

    assert row.passed is True
    assert row.pdf_ok is True
    assert row.acceptance_status == "done_pass"


def test_validate_job_rejects_tiny_pdf_even_when_z_gate_is_stale_valid(tmp_path: Path):
    run_dir = tmp_path / "jobs" / "v3_tiny_pdf" / "run"
    run_dir.mkdir(parents=True)
    _write_manifest(run_dir)
    _write_dossier(run_dir, z_validation={**_valid_pdf_validation(), "size": 2_048})
    _write_review(run_dir)
    (run_dir / "quality_review_log.md").write_text("# log\n\n## Skill Decision Trace\n\n- selected: paper-review-skill\n\n" + "reviewed\n" * 100, encoding="utf-8")
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 2_000)

    row = validate_jobs(tmp_path / "jobs", job_ids=["v3_tiny_pdf"])[0]

    assert row.passed is False
    assert row.pdf_ok is False
    assert "paper_draft_v0.pdf too small" in " | ".join(row.findings)


def test_validate_job_reports_missing_dossier_with_acceptance_fields(tmp_path: Path):
    row = validate_jobs(tmp_path / "jobs", job_ids=["v3_missing"])[0]

    assert row.passed is False
    assert row.acceptance_ok is False
    assert row.acceptance_status == "failed_repairable"
    assert row.findings == ["missing or invalid dossier.v3.json"]


def test_validate_job_rejects_review_dimension_scores_outside_zero_to_ten(tmp_path: Path):
    run_dir = tmp_path / "jobs" / "v3_bad_scores" / "run"
    run_dir.mkdir(parents=True)
    _write_manifest(run_dir)
    _write_dossier(run_dir, z_validation=_valid_pdf_validation())
    _write_review(run_dir, dimension_score=86)
    (run_dir / "quality_review_log.md").write_text("# log\n\n## Skill Decision Trace\n\n- selected: paper-review-skill\n\n" + "reviewed\n" * 100, encoding="utf-8")
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 120_000)

    row = validate_jobs(tmp_path / "jobs", job_ids=["v3_bad_scores"])[0]

    assert row.passed is False
    assert row.acceptance_status == "failed_repairable"
    assert "dimension score outside 0-10" in " | ".join(row.findings)


def test_manifest_backfill_includes_delivery_files_present_on_disk(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 120_000)
    (run_dir / "quality_review_round1.json").write_text("{}\n", encoding="utf-8")
    (run_dir / "quality_review_log.md").write_text("review\n", encoding="utf-8")

    write_artifact_manifest(
        run_dir,
        {
            "job_id": "v3_manifest",
            "domain": "paper",
            "artifacts": {"paper_draft_v0.pdf": {"path": "paper_draft_v0.pdf", "sha256": "abc"}},
        },
    )

    manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))

    assert sorted(manifest["artifacts"]) == [
        "paper_draft_v0.pdf",
        "quality_review_log.md",
        "quality_review_round1.json",
    ]
    assert len(manifest["artifacts"]["quality_review_log.md"]["sha256"]) == 64


def _write_manifest(run_dir: Path) -> None:
    (run_dir / "artifact_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "paperlab.artifact_manifest.v3.2",
                "artifacts": {
                    "paper_draft_v0.pdf": {"path": "paper_draft_v0.pdf", "sha256": "abc"},
                    "quality_review_round1.json": {"path": "quality_review_round1.json", "sha256": "def"},
                    "quality_review_log.md": {"path": "quality_review_log.md", "sha256": "ghi"},
                },
            }
        ),
        encoding="utf-8",
    )


def _write_dossier(run_dir: Path, *, z_validation: dict) -> None:
    phases = {
        "data": "done",
        "gap": "done",
        "structure": "done",
        "write": "done",
        "claim_evidence": "done",
        "render_gates": "done",
        "review_heal": "done",
        "format_repair": "done",
    }
    gate_reports = []
    for phase, gate_ids in {
        "claim_evidence": ["B"],
        "render_gates": ["C", "D", "F"],
        "review_heal": ["R"],
        "format_repair": ["Z"],
    }.items():
        gate_reports.append(
            {
                "phase": phase,
                "blocked": False,
                "failed_blocks": [],
                "results": [
                    {
                        "gate_id": gate_id,
                        "passed": True,
                        "severity": "block",
                        "details": "passed",
                        "evidence": {"validation": z_validation} if gate_id == "Z" else {},
                    }
                    for gate_id in gate_ids
                ],
            }
        )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(
            {
                "version": 3,
                "job_id": run_dir.parent.name,
                "domain": "paper",
                "phases": phases,
                "artifacts": {
                    "paper_draft_v0.pdf": {"path": "paper_draft_v0.pdf", "sha256": "abc"},
                    "quality_review_round1.json": {"path": "quality_review_round1.json", "sha256": "def"},
                    "quality_review_log.md": {"path": "quality_review_log.md", "sha256": "ghi"},
                },
                "evidence": {},
                "gate_reports": gate_reports,
                "delegations": [],
            }
        ),
        encoding="utf-8",
    )


def _write_review(run_dir: Path, *, dimension_score: float = 8.2) -> None:
    from engine_v3 import review_provenance

    (run_dir / "quality_review_log.md").write_text(
        "# Quality review log\n\n## Skill Decision Trace\n\n"
        "- selected: paper-review-skill\n\n" + "reviewed\n" * 100,
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
                    "selection_reason": "domain expert review before delivery",
                    "vip_capability_required": True,
                    "vip_capability_available": True,
                    "inputs_checked": ["paper_draft_v0.qmd", "references.bib"],
                    "reviewed_manuscript_sha256": review_provenance.manuscript_sha256(run_dir, ("paper_draft_v0.qmd",)),
                },
                "review_loop": {
                    "status": "passed",
                    "rounds": 1,
                    "reviewer_model": "hermes-reviewer",
                    "fixer_model": "hermes-fixer",
                    "independent_reviewer": True,
                    "floor_failed": False,
                },
                "dimensions": {
                    "academic_rigor": {"score": dimension_score},
                    "novelty_positioning": {"score": 8.1},
                    "experimental_completeness": {"score": 8.0},
                    "writing_quality": {"score": 8.4},
                    "practical_feasibility": {"score": 8.1},
                    "citation_accuracy": {"score": 8.5},
                    "format_compliance": {"score": 8.6},
                },
            }
        ),
        encoding="utf-8",
    )


def _valid_pdf_validation() -> dict:
    return {
        "valid": True,
        "producer": "xdvipdfmx",
        "creator": "LaTeX via pandoc",
        "raw_citation_count": 0,
        "unresolved_marker_count": 0,
        "numbered_section_detected": True,
        "table_widths": {"valid": True, "findings": []},
        "content_quality": {"valid": True, "findings": []},
        "findings": [],
    }
