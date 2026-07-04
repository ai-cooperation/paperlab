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
    # fresh repair budget: no prior repair delegations here, baseline 0
    assert dossier["evidence"]["repair_budget_baseline"] == {
        "render_gates": 0,
        "review_heal": 0,
        "format_repair": 0,
    }


def test_provenance_reset_grants_fresh_repair_budget_via_baseline(tmp_path: Path):
    from engine_v3.core.contracts import Dossier
    from engine_v3.core.orchestrator import _prior_repair_attempts, _repair_budget_baseline
    from revalidate_v3_batch import _prepare_review_provenance_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(
            {
                "phases": {"render_gates": "done", "review_heal": "done", "format_repair": "done"},
                "delegations": [
                    {"task_id": "render_gates:brain"},
                    {"task_id": "render_gates:repair:1"},
                    {"task_id": "render_gates:repair:2"},
                    {"task_id": "review_heal:repair:3"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "quality_review_round1.json").write_text(
        '{"delivery":"pass","review_loop":{"reviewer_model":"deterministic bounded final review"}}',
        encoding="utf-8",
    )

    assert _prepare_review_provenance_resume(tmp_path, "v3_job") is True

    raw = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert raw["evidence"]["repair_budget_baseline"] == {
        "render_gates": 2,
        "review_heal": 3,
        "format_repair": 0,
    }
    dossier = Dossier(job_id="v3_job", domain="paper")
    dossier.delegations.extend(raw["delegations"])
    dossier.evidence.update(raw["evidence"])
    # numbering continues from history, but the used budget starts fresh
    assert _prior_repair_attempts(dossier, "render_gates") == 2
    assert max(0, _prior_repair_attempts(dossier, "render_gates") - _repair_budget_baseline(dossier, "render_gates")) == 0


def test_provenance_reset_writes_baseline_even_when_phases_already_blocked(tmp_path: Path):
    from revalidate_v3_batch import _prepare_review_provenance_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(
            {
                "phases": {"render_gates": "blocked", "review_heal": "blocked", "format_repair": "blocked"},
                "delegations": [{"task_id": "render_gates:repair:2"}],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "quality_review_round1.json").write_text(
        '{"delivery":"pass","review_loop":{"reviewer_model":"deterministic bounded final review"}}',
        encoding="utf-8",
    )

    assert _prepare_review_provenance_resume(tmp_path, "v3_job") is True
    raw = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert raw["evidence"]["repair_budget_baseline"]["render_gates"] == 2


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


def _seed_valid_review(run_dir: Path) -> None:
    from engine_v3 import review_provenance

    stamp = review_provenance.manuscript_sha256(run_dir, ("paper_draft_v0.qmd",))
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
                    "selected_skill": "paper-review-and-citation-check",
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
        "# log\n\n## Skill Decision Trace\n\n- selected: paper-review-and-citation-check\n",
        encoding="utf-8",
    )


def test_content_findings_route_back_to_review_heal(tmp_path: Path):
    """Gate Z content findings (title language, caption overclaim, render
    overflow) need Hermes manuscript edits; format_repair cannot fix them in
    place. The revalidation driver must reset review_heal so the reviewer
    (with the strengthened skill) repairs and re-reviews."""
    from revalidate_v3_batch import _prepare_content_finding_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    # Chinese title on an English body = content finding
    (run_dir / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "校園正念介入研究"\n---\n\n' + ("English body text. " * 60),
        encoding="utf-8",
    )
    _seed_valid_review(run_dir)
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(
            {
                "phases": {"data": "done", "write": "done", "render_gates": "done", "review_heal": "done", "format_repair": "done"},
                "delegations": [{"task_id": "review_heal:repair:2"}],
            }
        ),
        encoding="utf-8",
    )

    changed = _prepare_content_finding_resume(tmp_path, "v3_job")

    assert changed is True
    dossier = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert dossier["phases"]["review_heal"] == "blocked"
    assert dossier["phases"]["format_repair"] == "blocked"
    assert dossier["phases"]["write"] == "done"
    assert dossier["evidence"]["repair_budget_baseline"]["review_heal"] == 2
    assert "content_finding_reset" in json.dumps(dossier["evidence"])


def test_no_content_reset_when_manuscript_clean(tmp_path: Path):
    from revalidate_v3_batch import _prepare_content_finding_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "School Mindfulness Study"\n---\n\n' + ("English body text. " * 60),
        encoding="utf-8",
    )
    _seed_valid_review(run_dir)
    (run_dir / "dossier.v3.json").write_text(
        json.dumps({"phases": {"review_heal": "done", "format_repair": "done"}}),
        encoding="utf-8",
    )

    assert _prepare_content_finding_resume(tmp_path, "v3_job") is False
    dossier = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert dossier["phases"]["review_heal"] == "done"


def test_revise_verdict_grants_retry_budget(tmp_path: Path):
    """Round 2 replayed round 1's findings verbatim: a valid-provenance revise
    verdict triggered no reset, so review_heal had zero budget and never
    re-ran. A revise verdict IS the retry signal."""
    from revalidate_v3_batch import _prepare_revise_verdict_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "paper_draft_v0.qmd").write_text("body", encoding="utf-8")
    (run_dir / "quality_review_round1.json").write_text(
        '{"delivery":"revise","p0_count":1,"review_loop":{"status":"failed_with_unresolved_p0","reviewer_model":"codex-reviewer"}}',
        encoding="utf-8",
    )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(
            {
                "phases": {"review_heal": "blocked", "format_repair": "blocked"},
                "delegations": [{"task_id": "review_heal:repair:3"}],
            }
        ),
        encoding="utf-8",
    )

    assert _prepare_revise_verdict_resume(tmp_path, "v3_job") is True
    dossier = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert dossier["evidence"]["repair_budget_baseline"]["review_heal"] == 3
    assert "revise_verdict_retry" in json.dumps(dossier["evidence"])


def test_revise_verdict_retry_stops_after_convergence_guard(tmp_path: Path):
    """Unlimited retries would loop forever on a manuscript that cannot pass;
    after two retries with a still-revise verdict, stop honestly (per the
    a64ad5b lesson: non-convergence defaults to a real deficiency, not a
    too-strict gate)."""
    from revalidate_v3_batch import _prepare_revise_verdict_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "quality_review_round1.json").write_text(
        '{"delivery":"revise","p0_count":1,"review_loop":{"status":"failed_with_unresolved_p0","reviewer_model":"codex-reviewer"}}',
        encoding="utf-8",
    )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(
            {
                "phases": {"review_heal": "blocked", "format_repair": "blocked"},
                "evidence": {
                    "quality_phase_resets": [
                        {"event": "revise_verdict_retry", "findings": []},
                        {"event": "revise_verdict_retry", "findings": []},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    assert _prepare_revise_verdict_resume(tmp_path, "v3_job") is False


def test_pass_verdict_does_not_trigger_revise_retry(tmp_path: Path):
    from revalidate_v3_batch import _prepare_revise_verdict_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "quality_review_round1.json").write_text(
        '{"delivery":"pass","p0_count":0,"review_loop":{"status":"passed","reviewer_model":"codex-reviewer"}}',
        encoding="utf-8",
    )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps({"phases": {"review_heal": "done", "format_repair": "done"}}),
        encoding="utf-8",
    )

    assert _prepare_revise_verdict_resume(tmp_path, "v3_job") is False


def _write_pass_review_with_loop(run_dir: Path, loop: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps({"delivery": "pass", "p0_count": 0, "review_loop": loop}),
        encoding="utf-8",
    )
    (run_dir / "quality_review_log.md").write_text("## Skill Decision Trace\nok", encoding="utf-8")


def test_pass_verdict_failing_loop_metadata_grants_retry(tmp_path: Path):
    """Round 18: a fully passing review (floor 80, p0=0, provenance ok) was
    Gate-R blocked solely on review_loop.independent_reviewer=false. No
    preparer owned that class - not revise (delivery=pass), not provenance
    (loop metadata is Gate R's, not provenance's) - so reruns replayed the
    same blocked state forever. A trusted pass verdict rejected for loop
    metadata IS a retry signal, same as a revise verdict."""
    from revalidate_v3_batch import _prepare_loop_metadata_resume

    run_dir = tmp_path / "v3_job" / "run"
    _write_pass_review_with_loop(
        run_dir,
        {
            "status": "passed",
            "rounds": 1,
            "reviewer_model": "gpt-5.5-codex-hermes",
            "fixer_model": "gpt-5.5-codex-hermes",
            "floor_failed": False,
            "independent_reviewer": False,
        },
    )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(
            {
                "phases": {"review_heal": "blocked", "format_repair": "blocked"},
                "delegations": [{"task_id": "review_heal:repair:2"}],
            }
        ),
        encoding="utf-8",
    )

    assert _prepare_loop_metadata_resume(tmp_path, "v3_job") is True
    dossier = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert dossier["evidence"]["repair_budget_baseline"]["review_heal"] == 2
    events = [r["event"] for r in dossier["evidence"]["quality_phase_resets"]]
    assert "loop_metadata_retry" in events


def test_loop_metadata_retry_stops_after_convergence_guard(tmp_path: Path):
    from revalidate_v3_batch import _prepare_loop_metadata_resume

    run_dir = tmp_path / "v3_job" / "run"
    _write_pass_review_with_loop(
        run_dir,
        {"status": "passed", "rounds": 1, "reviewer_model": "codex", "fixer_model": "codex", "floor_failed": False, "independent_reviewer": False},
    )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(
            {
                "phases": {"review_heal": "blocked", "format_repair": "blocked"},
                "evidence": {
                    "quality_phase_resets": [
                        {"event": "loop_metadata_retry", "findings": []},
                        {"event": "loop_metadata_retry", "findings": []},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    assert _prepare_loop_metadata_resume(tmp_path, "v3_job") is False


def test_loop_metadata_retry_not_triggered_when_loop_healthy(tmp_path: Path):
    from revalidate_v3_batch import _prepare_loop_metadata_resume

    run_dir = tmp_path / "v3_job" / "run"
    _write_pass_review_with_loop(
        run_dir,
        {
            "status": "passed",
            "rounds": 1,
            "reviewer_model": "codex-reviewer",
            "fixer_model": "codex-fixer",
            "floor_failed": False,
            "independent_reviewer": True,
        },
    )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps({"phases": {"review_heal": "blocked", "format_repair": "blocked"}}),
        encoding="utf-8",
    )

    assert _prepare_loop_metadata_resume(tmp_path, "v3_job") is False


def test_loop_metadata_retry_not_triggered_on_revise_verdict(tmp_path: Path):
    """Revise verdicts belong to _prepare_revise_verdict_resume; this preparer
    owns only the pass-verdict-rejected-for-loop-metadata class."""
    from revalidate_v3_batch import _prepare_loop_metadata_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "quality_review_round1.json").write_text(
        '{"delivery":"revise","p0_count":1,"review_loop":{"status":"blocked_revise","independent_reviewer":false}}',
        encoding="utf-8",
    )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps({"phases": {"review_heal": "blocked", "format_repair": "blocked"}}),
        encoding="utf-8",
    )

    assert _prepare_loop_metadata_resume(tmp_path, "v3_job") is False


def test_content_reset_uses_shared_validator_registry(tmp_path: Path):
    """Round 15: the revalidator's own hard-coded validator list missed the
    new citation-dump gate, so no reset fired and a dirty manuscript passed
    as all-done. Both consumers must share one registry."""
    from revalidate_v3_batch import _prepare_content_finding_resume

    run_dir = tmp_path / "v3_job" / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "paper_draft_v0.qmd").write_text(
        "## Bibliographic Scope Note\n\n"
        + " ".join("@ref%d" % i for i in range(20)) + "\n",
        encoding="utf-8",
    )
    (run_dir / "dossier.v3.json").write_text(
        json.dumps({"phases": {"review_heal": "done", "format_repair": "done"}}),
        encoding="utf-8",
    )

    assert _prepare_content_finding_resume(tmp_path, "v3_job") is True
    dossier = json.loads((run_dir / "dossier.v3.json").read_text(encoding="utf-8"))
    assert dossier["phases"]["review_heal"] == "blocked"
