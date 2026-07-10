"""ADR-001 slice-1 wiring regressions: the reviewed-out holes must stay closed.

Each test here is one reviewer-confirmed failure scenario from the v2/v3 adversarial
rounds — if any regresses, the patch treadmill (double-Abstract / stale-render /
infinite-heal-loop class) is back.
"""
from __future__ import annotations

import json
import re
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


# --- §8b: gate MOVE-vs-KEEP-READONLY dispositions (ADR-001 §V2-C) --------------

import json as _json
from engine_v3.pipelines.paper import (
    _section_source_relpaths,
    _validate_citation_distribution,
    _validate_citations_rendered,
    _validate_inline_heading_leakage,
    _validate_text_encoding,
    _validate_title_language,
)


def _cite_a_section(run: Path) -> None:
    """Give the new-arch run a real [@key] citation + matching bib so the MOVE'd
    citations_rendered gate is satisfied on the source surface."""
    (run / "references.bib").write_text("@article{k1, author={A B}, title={T}, year={2024}, journal={J}}\n", encoding="utf-8")
    p = run / "sections" / "part1.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n\nEvidence supports this [@k1].", encoding="utf-8")


def test_section_source_relpaths_empty_on_legacy(tmp_path: Path) -> None:
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections" / "introduction.md").write_text("legacy flat section", encoding="utf-8")
    assert _section_source_relpaths(tmp_path) == []  # no paper_meta.json -> legacy -> empty


def test_section_source_relpaths_from_meta_on_new_arch(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    rels = _section_source_relpaths(run)
    assert rels[0] == "sections/00_abstract.md"
    assert "sections/part1.md" in rels


def test_citations_rendered_moves_to_sections_on_new_arch(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    from engine_v3.assembly import assemble_paper
    # sections have NO citation yet -> gate must FLAG (reading sources, per §V2-C)
    (run / "references.bib").write_text("@article{k1, author={A B}, year={2024}}\n", encoding="utf-8")
    assemble_paper(run)
    assert _validate_citations_rendered(run)["valid"] is False
    # add a citation to a SOURCE section -> gate clears (fix + gate same surface)
    _cite_a_section(run)
    assemble_paper(run)
    assert _validate_citations_rendered(run)["valid"] is True


def test_citation_distribution_keeps_reading_generated_qmd(tmp_path: Path) -> None:
    """Cross-boundary dump is a POST-JOIN property: the gate must read the generated
    qmd (KEEP-readonly), not per-section sources."""
    run = make_run(tmp_path)
    from engine_v3.assembly import assemble_paper
    _cite_a_section(run)
    assemble_paper(run)
    assert _validate_citation_distribution(run)["valid"] is True
    # a citation dump spanning the assembled body is caught on the generated surface
    dump = "\n\n" + " ".join("[@k%d]" % i for i in range(40)) + "\n"
    (run / "paper_draft_v0.qmd").write_text(
        (run / "paper_draft_v0.qmd").read_text(encoding="utf-8") + dump, encoding="utf-8"
    )
    assert _validate_citation_distribution(run)["valid"] is False


def test_title_language_asserts_rendered_matches_meta(tmp_path: Path) -> None:
    """New-arch title source of truth is paper_meta.json; the rendered springer
    title must equal it (guards render_springer._old_title fallback)."""
    run = make_run(tmp_path)
    from engine_v3.assembly import assemble_paper, ir_render_values
    import render_springer
    _cite_a_section(run)
    assemble_paper(run)
    render_springer.normalize_frontmatter(run, {}, ir_values=ir_render_values(run))
    assert _validate_title_language(run)["valid"] is True
    # simulate the _old_title fallback: springer frontmatter carries a WRONG title
    sp = run / "paper_springer.qmd"
    txt = sp.read_text(encoding="utf-8")
    txt = re.sub(r'(?m)^title:\s*".*?"', 'title: "Totally Different Fallback Topic"', txt, count=1)
    sp.write_text(txt, encoding="utf-8")
    result = _validate_title_language(run)
    assert result["valid"] is False
    assert "does not match" in " ".join(result["findings"])


def test_text_encoding_scans_section_sources_on_new_arch(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    from engine_v3.assembly import assemble_paper
    _cite_a_section(run)
    assemble_paper(run)
    assert _validate_text_encoding(run)["valid"] is True
    # mojibake introduced into a SOURCE section is caught (scan covers sources)
    (run / "sections" / "part2.md").write_text("Body with broken UTF-8 â€ dash here.", encoding="utf-8")
    result = _validate_text_encoding(run)
    assert result["valid"] is False
    assert any("part2" in f for f in result["findings"])


def test_inline_heading_leak_scans_sources_but_ignores_source_map(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    from engine_v3.assembly import assemble_paper
    _cite_a_section(run)
    assemble_paper(run)
    # assembler output (with <!-- SOURCE --> markers) must NOT false-flag
    assert _validate_inline_heading_leakage(run)["valid"] is True
    # a genuine glued heading in a SOURCE section IS caught
    (run / "sections" / "part2.md").write_text("Prose ends abruptly. ## Sneaky Heading", encoding="utf-8")
    result = _validate_inline_heading_leakage(run)
    assert result["valid"] is False


# --- §9: healer round-trip contract (Q5 CRITICAL) -----------------------------


def test_generated_qmds_not_in_review_heal_outputs() -> None:
    """The healer's allowed write set must EXCLUDE the generated artifacts — else a
    direct edit survives one phase then ensure_assembled clobbers it, breaking the
    round-trip (ADR-001 §7 Q5 CRITICAL)."""
    outputs = set(paper_pipeline.REVIEW_HEAL_OUTPUTS)
    assert "paper_draft_v0.qmd" not in outputs
    assert "paper_springer.qmd" not in outputs
    # sources the healer DOES edit are present
    assert "paper_meta.json" in outputs
    assert "sections/00_abstract.md" in outputs
    assert "references.bib" in outputs  # bib fix still allowed (round 17)


def test_write_source_outputs_excludes_generated_draft() -> None:
    assert "paper_draft_v0.qmd" not in paper_pipeline.WRITE_SOURCE_OUTPUTS
    assert "paper_meta.json" in paper_pipeline.WRITE_SOURCE_OUTPUTS


def test_heal_prompt_directs_edits_to_sources_not_generated() -> None:
    prompt = paper_pipeline.REVIEW_HEAL_PROMPT
    assert "Do NOT edit paper_draft_v0.qmd" in prompt
    assert "GENERATED" in prompt and "editing the SOURCE files" in prompt


def test_round_trip_source_edit_then_reassemble_reaches_gate(tmp_path: Path) -> None:
    """End-to-end round-trip: a source edit between phases is re-derived into the qmd
    (already covered by test_heal_edit_propagates_to_gate_surface) AND a stale direct
    qmd edit is overwritten by the next ensure_assembled."""
    from engine_v3.assembly import assemble_paper, ensure_assembled

    run = make_run(tmp_path)
    assemble_paper(run)
    # simulate a (forbidden) direct qmd edit — it must NOT survive re-assembly
    (run / "paper_draft_v0.qmd").write_text("HAND EDIT THAT SHOULD VANISH", encoding="utf-8")
    ensure_assembled(run)
    draft = (run / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "HAND EDIT THAT SHOULD VANISH" not in draft  # clobbered by re-assembly
    assert "## Abstract" in draft  # regenerated from sources


# --- stale-springer class (2026-07-10 rerun validation: blocked 395d + e2307) --


def test_springer_regenerated_from_fresh_draft_on_new_arch(tmp_path: Path) -> None:
    """A migrated run carries the ORIGINAL run's paper_springer.qmd. Gates and the
    reviewer judge it, but the healer may not write it (Q5) and nothing re-derived
    it before render — an unfixable finding that burned review rounds on two jobs.
    _ensure_paper_springer_source_v3_2 must REGENERATE springer from the fresh
    draft + IR values on every call for a new-arch run."""
    import json as _j

    run = make_run(tmp_path)
    (run / "references.bib").write_text("@article{k1, author={A, B}, year={2024}}", encoding="utf-8")
    (run / "research_contract.json").write_text(_j.dumps({"topic": "t"}), encoding="utf-8")
    from engine_v3.assembly import assemble_paper

    assemble_paper(run)
    # the stale original-run springer with a defect only IT carries
    (run / "paper_springer.qmd").write_text(
        "---\ntitle: stale\n---\n\nSTALE DEFECT ONLY IN OLD SPRINGER\n", encoding="utf-8"
    )
    changed = paper_pipeline._ensure_paper_springer_source_v3_2(run)
    springer = (run / "paper_springer.qmd").read_text(encoding="utf-8")
    assert changed
    assert "STALE DEFECT ONLY IN OLD SPRINGER" not in springer  # regenerated
    assert "abstract:" in springer.split("---")[1]  # IR abstract in frontmatter
    assert "substantive sentence" in springer  # body derived from fresh draft


def test_springer_regen_skipped_when_sources_cannot_assemble(tmp_path: Path) -> None:
    """meta exists but sources broken -> assembly block report gates the run; the
    springer must be left alone, not derived from a potentially stale draft."""
    run = make_run(tmp_path)
    (run / "sections" / "00_abstract.md").unlink()  # break assembly
    (run / "paper_springer.qmd").write_text("---\ntitle: old\n---\n\nold body\n", encoding="utf-8")
    changed = paper_pipeline._ensure_paper_springer_source_v3_2(run)
    assert not changed
    assert "old body" in (run / "paper_springer.qmd").read_text(encoding="utf-8")
