"""ADR-001 slice-1 wiring regressions: the reviewed-out holes must stay closed.

Each test here is one reviewer-confirmed failure scenario from the v2/v3 adversarial
rounds — if any regresses, the patch treadmill (double-Abstract / stale-render /
infinite-heal-loop class) is back.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3.assembly import write_render_manifest
from engine_v3.core import BrainTask, DossierStore, PhaseSpec, RuntimeContext
from engine_v3.core.orchestrator import EngineV3Orchestrator
from engine_v3.packs import paper_artifacts
from engine_v3.packs.paper import _gate_delivery
from engine_v3.pipelines import paper as paper_pipeline
from engine_v3.runtimes.mock import MockRuntime

from test_assembly_assembler import ABSTRACT_TEXT, make_run
from test_assembly_manifest import _finish_render

pytestmark = pytest.mark.unit


# --- V4-C: done phase must re-run when the delivery is stale ------------------


def _resume_orchestrator(tmp_path: Path, calls: list[str], probe) -> EngineV3Orchestrator:
    def handler(task: BrainTask, context: RuntimeContext):
        calls.append(task.phase)
        return {}

    store = DossierStore(tmp_path)
    dossier = store.create(job_id="job-1", domain="paper")
    dossier.mark_phase("format_repair", "done")
    store.save(dossier)
    return EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=object(),
        phases=[PhaseSpec(id="format_repair", handler=handler, staleness_probe=probe)],
        dossier_store=store,
    )


def test_resume_skips_done_phase_when_delivery_fresh(tmp_path: Path) -> None:
    calls: list[str] = []
    orchestrator = _resume_orchestrator(tmp_path, calls, probe=lambda run_dir: False)
    orchestrator.run(job_id="job-1", resume=True)
    assert calls == []  # fresh -> phase_skip_done preserved (no false re-render)


def test_resume_reruns_done_phase_when_delivery_stale(tmp_path: Path) -> None:
    calls: list[str] = []
    orchestrator = _resume_orchestrator(tmp_path, calls, probe=lambda run_dir: True)
    orchestrator.run(job_id="job-1", resume=True)
    assert calls == ["format_repair"]  # stale -> phase_skip_done is refused


def test_resume_skip_unchanged_without_probe(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(task: BrainTask, context: RuntimeContext):
        calls.append(task.phase)
        return {}

    store = DossierStore(tmp_path)
    dossier = store.create(job_id="job-1", domain="paper")
    dossier.mark_phase("phase-0", "done")
    store.save(dossier)
    EngineV3Orchestrator(
        runtime=MockRuntime(),
        domain_pack=object(),
        phases=[PhaseSpec(id="phase-0", handler=handler)],
        dossier_store=store,
    ).run(job_id="job-1", resume=True)
    assert calls == []  # legacy phases keep today's skip semantics


# --- V4-B: Gate Z blocks on delivery-freshness findings -----------------------


def _z_evidence(delivery_freshness) -> dict:
    return {
        "artifacts": {"paper_draft_v0.pdf": {"sha256": "abc"}},
        "evidence": {
            "delivery_pdf_validation": {"valid": True, "findings": []},
            "review_freshness": {"fresh": True, "findings": []},
            "delivery_freshness": delivery_freshness,
        },
    }


def test_gate_z_blocks_on_stale_delivery() -> None:
    result = _gate_delivery(_z_evidence(["delivery is stale: render sources changed"]))
    assert not result.passed
    assert "stale" in result.details


def test_gate_z_passes_on_empty_or_absent_freshness() -> None:
    assert _gate_delivery(_z_evidence([])).passed
    legacy = _z_evidence(None)
    del legacy["evidence"]["delivery_freshness"]
    assert _gate_delivery(legacy).passed  # legacy dossiers never blocked by the new conjunct


# --- V4-C root: review stamp binds to SOURCES, not the generated qmd ----------


def test_review_stamp_files_are_sources_on_new_arch_runs(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    files = paper_artifacts.review_manuscript_files(run)
    assert files[0] == "paper_meta.json"
    assert "sections/00_abstract.md" in files
    assert "paper_draft_v0.qmd" not in files  # generated artifact is OUT of the stamp


def test_review_stamp_files_legacy_fallback(tmp_path: Path) -> None:
    assert paper_artifacts.review_manuscript_files(tmp_path) == paper_artifacts.MANUSCRIPT_FILES


def test_regenerating_qmd_does_not_move_source_stamp(tmp_path: Path) -> None:
    """agy's fatal-loop scenario: a deterministic re-assembly (qmd rewrite) must not
    change the review-stamp hash — only a SOURCE edit may."""
    from engine_v3 import review_provenance
    from engine_v3.assembly import assemble_paper

    run = make_run(tmp_path)
    assemble_paper(run)
    files = paper_artifacts.review_manuscript_files(run)
    before = review_provenance.manuscript_sha256(run, files)
    (run / "paper_draft_v0.qmd").write_text("totally rewritten", encoding="utf-8")
    assert review_provenance.manuscript_sha256(run, files) == before
    (run / "sections" / "part1.md").write_text("## P\n\n" + "edited. " * 100, encoding="utf-8")
    assert review_provenance.manuscript_sha256(run, files) != before


# --- V4-C: heal edit propagates through the phase handler (no infinite loop) --


def test_heal_edit_propagates_to_gate_surface(tmp_path: Path) -> None:
    """The v3 blocker both reviewers converged on: after a healer edits a section,
    the next qmd-reading phase must judge a re-derived draft, not the stale one."""
    run = make_run(tmp_path)
    (run / "references.bib").write_text("@a{k1, author={A}, year={2024}}", encoding="utf-8")
    (run / "real_experiments").mkdir(exist_ok=True)
    (run / "real_experiments" / "real_results.json").write_text("{}", encoding="utf-8")
    (run / "research_contract.json").write_text(json.dumps({"topic": "t"}), encoding="utf-8")

    task = BrainTask(task_id="write:1", phase="write", prompt="p")
    context = RuntimeContext(job_id="job-1", run_dir=run)
    paper_pipeline._collect_gate_inputs(task, context)
    assert "substantive sentence" in (run / "paper_draft_v0.qmd").read_text(encoding="utf-8")

    # healer edits a SOURCE section between phases
    (run / "sections" / "part1.md").write_text(
        "## Part 1\n\n" + "healer corrected claim. " * 95, encoding="utf-8"
    )
    task2 = BrainTask(task_id="render_gates:1", phase="render_gates", prompt="p")
    result = paper_pipeline._collect_gate_inputs(task2, context)
    draft = (run / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "healer corrected claim." in draft  # gates judge current sources
    assert result["gate_inputs"]["assembly"]["ok"] is True


# --- V4-A: batch reset = existing failure trigger OR staleness ----------------


class _Validation:
    def __init__(self, passed: bool, findings=(), status: str = "done"):
        self.passed = passed
        self.findings = list(findings)
        self.status = status


def _batch_job(tmp_path: Path, *, stale: bool) -> tuple[Path, str]:
    jobs_dir = tmp_path / "jobs"
    run = jobs_dir / "job-1" / "run"
    run.mkdir(parents=True)
    make_run(run)
    _finish_render(run)
    if stale:
        (run / "sections" / "part1.md").write_text("## P\n\n" + "moved. " * 100, encoding="utf-8")
    (run / "dossier.v3.json").write_text(
        json.dumps({"phases": {"format_repair": "done"}}), encoding="utf-8"
    )
    return jobs_dir, "job-1"


def test_batch_reset_fires_on_passed_but_stale(tmp_path: Path) -> None:
    import revalidate_v3_batch as rvb

    jobs_dir, job_id = _batch_job(tmp_path, stale=True)
    assert rvb._prepare_acceptance_repair_resume(jobs_dir, job_id, _Validation(passed=True))
    dossier = json.loads((jobs_dir / job_id / "run" / "dossier.v3.json").read_text())
    assert dossier["phases"]["format_repair"] == "blocked"


def test_batch_reset_not_fired_when_passed_and_fresh(tmp_path: Path) -> None:
    import revalidate_v3_batch as rvb

    jobs_dir, job_id = _batch_job(tmp_path, stale=False)
    assert not rvb._prepare_acceptance_repair_resume(jobs_dir, job_id, _Validation(passed=True))
    dossier = json.loads((jobs_dir / job_id / "run" / "dossier.v3.json").read_text())
    assert dossier["phases"]["format_repair"] == "done"


def test_batch_reset_still_fires_on_gate_logic_failure_with_fresh_sources(tmp_path: Path) -> None:
    """codex's V2-A blocker: 'gate changed, sources unchanged' must STILL re-render.
    Staleness was ADDED as a trigger, never substituted."""
    import revalidate_v3_batch as rvb

    jobs_dir, job_id = _batch_job(tmp_path, stale=False)
    validation = _Validation(
        passed=False, findings=["paper_draft_v0.pdf PDF content-quality validation missing"]
    )
    assert rvb._prepare_acceptance_repair_resume(jobs_dir, job_id, validation)
    dossier = json.loads((jobs_dir / job_id / "run" / "dossier.v3.json").read_text())
    assert dossier["phases"]["format_repair"] == "blocked"
