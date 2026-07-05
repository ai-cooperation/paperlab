from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from engine_v3.core import DossierStore
from engine_v3.core.orchestrator import EngineV3Orchestrator
from engine_v3.core import BrainTask, RuntimeContext
from engine_v3.packs.paper import PaperPack
from engine_v3.pipelines.paper import (
    BOUNDED_GOLDEN_OUTPUTS,
    DATA_OUTPUTS,
    FULL_PIPELINE_OUTPUTS,
    RENDER_GATE_OUTPUTS,
    WRITE_OUTPUTS,
    bounded_golden_pipeline,
    full_paper_pipeline,
    _validate_delivery_pdf,
    _validate_table_widths,
)
from engine_v3.runtimes.codex_cli import CliRunResult, CodexCliRuntime
import engine_v3.pipelines.paper as paper_pipeline

pytestmark = pytest.mark.unit


def test_full_pipeline_data_prompt_includes_gate_a_acceptance_criteria():
    data_phase = full_paper_pipeline()[0]

    assert data_phase.id == "data"
    assert data_phase.gate_ids == ["A", "E", "G"]
    assert "35" in data_phase.prompt
    assert "doi_real_rate" in data_phase.prompt
    assert "0.80" in data_phase.prompt


def test_collect_gate_inputs_only_reports_data_substeps_for_data_phase(tmp_path: Path):
    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="claim_evidence", task_id="claim_evidence:brain"),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result["substeps"] == []


def test_structure_handler_backfills_phase4_structure_when_hermes_writes_nothing(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "research_contract.json").write_text(
        json.dumps(
            {
                "topic": "DTP3 Immunization Coverage and Under-Five Mortality",
                "research_question": "Estimate lagged DTP3 associations with under-five mortality in a global panel.",
                "contribution": "DTP3-specific two-way fixed-effects panel benchmark.",
                "target_journal": "Q2-Q3 stable target journal",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "phase3_positioning.md").write_text(
        "# Research Positioning\n\n## Gap Matrix\n\nG1: Exposure specificity.\nG2: Timing gap.",
        encoding="utf-8",
    )
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "sample": {"n_country_year_complete": 5320, "n_countries": 235},
                "main_twfe_coefficients": [{"term": "dtp3_lag1", "coef_log_points": -0.01}],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "references.bib").write_text("@article{ref,title={Reference}}\n", encoding="utf-8")
    (run_dir / "doi_audit.json").write_text('{"records":[{"doi":"10.1000/x","validation_count":2}]}', encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="structure", task_id="structure:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    structure = (run_dir / "phase4_structure.md").read_text(encoding="utf-8")
    assert "DTP3 Immunization Coverage" in structure
    assert "Claim Boundaries" in structure
    assert "phase3_positioning.md" in structure
    assert "fig_prisma_flow" in structure


def test_gap_handler_backfills_phase3_positioning_when_hermes_writes_nothing(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "research_contract.json").write_text(
        json.dumps(
            {
                "topic": "Internet Penetration and Secondary School Completion",
                "research_question": "Estimate a bounded evidence-supported relationship.",
                "contribution": "Conservative V3.2 positioning.",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text(
        '{"analysis_type":"deterministic_reference_evidence_map","synthesis":{"numeric_effect_count":0}}',
        encoding="utf-8",
    )
    (run_dir / "references.bib").write_text("@article{ref,title={Reference}}\n", encoding="utf-8")
    (run_dir / "doi_audit.json").write_text('{"records":[{"doi":"10.1000/x","validation_count":2}]}', encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="gap", task_id="gap:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    positioning = (run_dir / "phase3_positioning.md").read_text(encoding="utf-8")
    assert "Research Positioning" in positioning
    assert "Gap Matrix" in positioning
    assert "Claim Boundaries" in positioning
    assert "deterministic_reference_evidence_map" in positioning


def test_write_handler_does_not_synthesize_content_when_hermes_writes_nothing(tmp_path: Path):
    """The 2026-07-02 Potemkin root: the write fallback used to synthesize a
    whole boilerplate manuscript. Now missing sections stay missing so the
    missing-output repair loop routes the work back to Hermes."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "research_contract.json").write_text(
        json.dumps(
            {
                "topic": "DTP3 Immunization Coverage and Under-Five Mortality",
                "research_question": "Estimate bounded associations.",
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "phase3_positioning.md").write_text("# Research Positioning\n", encoding="utf-8")
    (run_dir / "phase4_structure.md").write_text("# Phase 4 Structure\n", encoding="utf-8")
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps({"sample": {"n_country_year_complete": 5320, "n_countries": 235}}),
        encoding="utf-8",
    )
    (run_dir / "references.bib").write_text(
        "@article{refA,title={Reference A},author={Author, A.},year={2024}}\n",
        encoding="utf-8",
    )

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="write", task_id="write:brain", expected_outputs=list(WRITE_OUTPUTS)),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    assert not (run_dir / "paper_draft_v0.qmd").is_file()
    assert not (run_dir / "sections" / "introduction.md").is_file()
    assert "paper_draft_v0.qmd" not in result["artifacts"]


def test_write_handler_composes_qmd_from_substantive_hermes_sections(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "research_contract.json").write_text(
        json.dumps({"topic": "DTP3 Coverage Study"}), encoding="utf-8"
    )
    (run_dir / "references.bib").write_text(
        "@article{refA,title={Reference A},author={Author, A.},year={2024}}\n",
        encoding="utf-8",
    )
    (run_dir / "sections").mkdir()
    real_paragraph = ("This section reports substantive Hermes-written analysis content. " * 12).strip()
    for name in ("introduction", "related_work", "methods", "results", "discussion", "limitations", "conclusion"):
        (run_dir / "sections" / ("%s.md" % name)).write_text(
            "## %s\n\n%s\n" % (name.title(), real_paragraph), encoding="utf-8"
        )

    changed = paper_pipeline._ensure_write_outputs_v3_2(run_dir)

    assert changed is True
    qmd = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "substantive Hermes-written analysis content" in qmd
    assert "link-citations: true" in qmd


def test_write_handler_refuses_to_compose_from_outline_fragments(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "research_contract.json").write_text(
        json.dumps({"topic": "DTP3 Coverage Study"}), encoding="utf-8"
    )
    (run_dir / "sections").mkdir()
    for name in ("introduction", "related_work", "methods", "results", "discussion", "limitations", "conclusion"):
        (run_dir / "sections" / ("%s.md" % name)).write_text("## Outline\n\n- todo\n", encoding="utf-8")

    changed = paper_pipeline._ensure_write_outputs_v3_2(run_dir)

    assert changed is False
    assert not (run_dir / "paper_draft_v0.qmd").is_file()


def test_render_handler_backfills_paper_springer_from_draft(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text(
        "---\ntitle: Test\n---\n\n## Intro\n\nTraceable text.",
        encoding="utf-8",
    )

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="render_gates", task_id="render_gates:brain", expected_outputs=list(RENDER_GATE_OUTPUTS)),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    springer = (run_dir / "paper_springer.qmd").read_text(encoding="utf-8")
    assert "link-citations: true" in springer
    assert "number-sections: true" in springer
    assert "For V3.2 production quality" not in springer
    assert springer.count("## Evidence Boundary Notes") <= 1
    # No filler tables are injected any more: a table-less manuscript must FAIL
    # table validation so the gate routes repair back to the writer, instead of
    # being padded past Gate Z with traceability filler tables.
    assert _validate_table_widths(run_dir)["valid"] is False
    assert "Traceability Tables" not in springer
    assert "paper_springer.qmd" in result["artifacts"]


def _seed_review_heal_run(run_dir: Path, *, delivery: str, body: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    qmd = '---\ntitle: "T"\nbibliography: references.bib\n---\n\n# Introduction\n\n' + body
    (run_dir / "paper_draft_v0.qmd").write_text(qmd, encoding="utf-8")
    (run_dir / "paper_springer.qmd").write_text(qmd, encoding="utf-8")
    (run_dir / "references.bib").write_text(
        "@article{zhang2020,title={A},year={2020}}\n", encoding="utf-8"
    )
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps(
            {
                "delivery": delivery,
                "p0_count": 0 if delivery == "pass" else 1,
                "floor_100": 84,
                "findings": [
                    {
                        "severity": "P2",
                        "issue": "prose polish",
                        "target_content": "The design was proposed by prior work [@zhang2020].",
                        "replacement_content": "Prior work proposed the design.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "quality_review_log.md").write_text("## Skill Decision Trace\nok\n", encoding="utf-8")


def test_gate_collection_must_not_mutate_a_pass_reviewed_manuscript(tmp_path: Path):
    """Round 5 on v3_0f6a0c83f9cf: Hermes wove the 35 verified citations into
    the body and issued a fresh pass review; at gate collection the harness
    re-applied the review's target/replacement prescriptions to the PASS
    manuscript and stripped the just-woven @citekeys (all three files share
    the 21:13:24 mtime). The harness violated the same review-last ordering
    contract the prompts pin on Hermes: once the verdict is pass, the
    manuscript is final and harness repairs must not touch it."""
    run_dir = tmp_path / "run"
    body = "The design was proposed by prior work [@zhang2020]."
    _seed_review_heal_run(run_dir, delivery="pass", body=body)
    before = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    after = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert after == before
    assert "[@zhang2020]" in after


def test_gate_collection_still_applies_prescriptions_on_revise_verdicts(tmp_path: Path):
    run_dir = tmp_path / "run"
    body = "The design was proposed by prior work [@zhang2020]."
    _seed_review_heal_run(run_dir, delivery="revise", body=body)

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    after = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "Prior work proposed the design." in after


def test_pending_findings_computed_after_harness_mutations(tmp_path: Path):
    """The pending-findings bridge must describe the manuscript state the gate
    will actually judge: on a revise verdict the harness applies replacements,
    so the bridge runs after them (round 5: the bridge saw citations present,
    then the replacement stripped them, and the citation finding vanished
    from the worklist)."""
    run_dir = tmp_path / "run"
    body = "The design was proposed by prior work [@zhang2020]."
    _seed_review_heal_run(run_dir, delivery="revise", body=body)

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    # The replacement stripped the only citation; the bridge must report it.
    pending = result["gate_inputs"]["pending_content_findings"]
    assert any("no inline citations rendered" in f for f in pending)


def test_data_harness_backfills_minimal_real_results_and_figures_from_verified_refs(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "research_contract.input.json").write_text('{"topic":"energy baselines"}', encoding="utf-8")
    (run_dir / "references.bib").write_text(
        "\n".join(
            '@article{ref%d,title={Reference %d},year={202%d},doi={10.1000/ref%d}}'
            % (idx, idx, idx % 10, idx)
            for idx in range(35)
        ),
        encoding="utf-8",
    )
    (run_dir / "doi_audit.json").write_text(
        '{"summary":{"included_references":35,"included_with_two_or_more_validations":35}}',
        encoding="utf-8",
    )

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="data", task_id="data:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    completeness = result["gate_inputs"]["data_completeness"]
    assert completeness["status"] == "done"
    assert completeness["missing_outputs"] == []
    real_results = (run_dir / "real_experiments" / "real_results.json").read_text(encoding="utf-8")
    assert "bibliometric_evidence_map" in real_results
    for rel in DATA_OUTPUTS:
        assert (run_dir / rel).is_file(), rel


def test_claim_evidence_handler_downgrades_unsupported_strong_causal_sentence(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    draft = (
        "Prior work demonstrates that vaccination and child survival are linked, "
        "explains why immunization access varies, and provides tools for global panel modelling."
    )
    (run_dir / "paper_draft_v0.qmd").write_text(draft, encoding="utf-8")
    (run_dir / "paper_springer.qmd").write_text(draft, encoding="utf-8")
    (run_dir / "claim_evidence_map.md").write_text("| Claim | Evidence |\n|---|---|\n", encoding="utf-8")
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text('{"max_poolable_k":0}', encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="claim_evidence", task_id="claim_evidence:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    repaired = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "demonstrates that" not in repaired
    assert "suggests that" in repaired

    from framework import run_gates
    from packs.paper import PaperPack

    report = run_gates(PaperPack(), paper_pipeline.paperctl._build_dossier(run_dir), only={"B"})
    assert report.blocked is False


def test_claim_evidence_handler_softens_fallback_universal_claim_boundary(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    draft = "## Limitations\n\nThe main limitation is that every claim is constrained by the artifacts available in this run."
    (run_dir / "paper_draft_v0.qmd").write_text(draft, encoding="utf-8")
    (run_dir / "paper_springer.qmd").write_text(draft, encoding="utf-8")
    (run_dir / "claim_evidence_map.md").write_text("| Claim | Evidence |\n|---|---|\n", encoding="utf-8")
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text('{"reference_count":40}', encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="claim_evidence", task_id="claim_evidence:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    repaired = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "every claim" not in repaired
    assert "manuscript claims are constrained" in repaired

    from framework import run_gates
    from packs.paper import PaperPack

    report = run_gates(PaperPack(), paper_pipeline.paperctl._build_dossier(run_dir), only={"B"})
    assert report.blocked is False


def test_render_gate_handler_normalizes_thousands_commas_before_logic_audit(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for rel in ["paper_draft_v0.qmd", "paper_springer.qmd", "sections/results.md"]:
        path = run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("The analysis used 5,432 observations from 237 countries.", encoding="utf-8")
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text(
        '{"sample":{"analysis_observations":5432,"analysis_countries":237}}',
        encoding="utf-8",
    )

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="render_gates", task_id="render_gates:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    assert "5,432" not in (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "5432 observations" in (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")


def test_review_heal_applies_exact_replacements_but_keeps_delivery_revise(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    target = "The method is production ready without further validation."
    replacement = "The method is suitable for continued validation after the current checks."
    for rel in ["paper_draft_v0.qmd", "paper_springer.qmd", "sections/discussion.md"]:
        path = run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(target, encoding="utf-8")
    (run_dir / "quality_review_round1.json").write_text(
        '{"p0_count":0,"delivery":"revise","floor_100":82.0,'
        '"review_loop":{"status":"round1_complete_revise_required","rounds":1,'
        '"reviewer_model":"codex-reviewer","fixer_model":"hermes","independent_reviewer":true,'
        '"floor_failed":true},'
        '"dimensions":{'
        '"academic_rigor":{"score":8.2},"novelty_positioning":{"score":8.0},'
        '"experimental_completeness":{"score":7.0},"writing_quality":{"score":8.6},'
        '"practical_feasibility":{"score":8.6},"citation_accuracy":{"score":8.4},'
        '"format_compliance":{"score":6.8}},'
        '"findings":[{"severity":"P1","target_content":"%s","replacement_content":"%s"}]}'
        % (target, replacement),
        encoding="utf-8",
    )
    (run_dir / "quality_review_log.md").write_text("round 1\n", encoding="utf-8")

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    review = result["gate_inputs"]["review"]
    assert review["delivery"] == "revise"
    assert review["review_loop"]["status"] == "repairs_applied_rereview_required"
    assert review["deterministic_review_heal"]["rereview_required"] is True
    assert "deterministic_review_heal" in (run_dir / "quality_review_log.md").read_text(encoding="utf-8")
    assert replacement in (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")


def test_review_heal_regenerates_flagged_figures_but_requires_rereview(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text(
        '{"reference_count":40}',
        encoding="utf-8",
    )
    fig_dir = run_dir / "figures"
    fig_dir.mkdir()
    for stem in ["fig_prisma_flow", "fig_method_overview"]:
        (fig_dir / ("%s.svg" % stem)).write_text("<svg>bad</svg>", encoding="utf-8")
        (fig_dir / ("%s.png" % stem)).write_bytes(b"bad")
    (run_dir / "quality_review_round1.json").write_text(
        '{"p0_count":0,"delivery":"revise","floor_100":82.0,'
        '"review_loop":{"status":"round1_complete_revise_required","rounds":1,'
        '"reviewer_model":"codex-reviewer","fixer_model":"hermes","independent_reviewer":"internal",'
        '"floor_failed":true},'
        '"dimensions":{'
        '"academic_rigor":{"score":8.2},"novelty_positioning":{"score":8.0},'
        '"experimental_completeness":{"score":7.0},"writing_quality":{"score":8.6},'
        '"practical_feasibility":{"score":8.6},"citation_accuracy":{"score":8.4},'
        '"format_compliance":{"score":6.8}},'
        '"findings":[{"severity":"P1","location":"figures/fig_prisma_flow.png",'
        '"issue":"overlap","concrete_fix":"Regenerate figures/fig_prisma_flow.svg and figures/fig_prisma_flow.png"},'
        '{"severity":"P1","location":"figures/fig_method_overview.png",'
        '"issue":"clipping","concrete_fix":"Regenerate figures/fig_method_overview.svg and figures/fig_method_overview.png"}]}',
        encoding="utf-8",
    )
    (run_dir / "quality_review_log.md").write_text("round 1\n", encoding="utf-8")

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    review = result["gate_inputs"]["review"]
    assert review["delivery"] == "revise"
    assert review["review_loop"]["status"] == "repairs_applied_rereview_required"
    assert review["review_loop"]["independent_reviewer"] is False
    assert (fig_dir / "fig_prisma_flow.png").stat().st_size > 1000
    assert "PRISMA-style evidence screening flow" in (fig_dir / "fig_prisma_flow.svg").read_text(encoding="utf-8")
    assert "Evidence acquisition and verification workflow" in (fig_dir / "fig_method_overview.svg").read_text(encoding="utf-8")
    assert "ESCO" not in (fig_dir / "fig_method_overview.svg").read_text(encoding="utf-8")
    assert "deterministic_review_heal" in (run_dir / "quality_review_log.md").read_text(encoding="utf-8")


def test_review_heal_removes_flagged_out_of_domain_citation_then_requires_rereview(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    sentence = "External-validity caveats are informed by a weak transfer reference @Hasan2020Diabetes."
    for rel in ["paper_draft_v0.qmd", "paper_springer.qmd", "sections/discussion.md"]:
        path = run_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sentence + "\n\nA retained domain sentence remains.\n", encoding="utf-8")
    (run_dir / "references.bib").write_text(
        "@article{Hasan2020Diabetes,\n  title={Diabetes ML},\n  year={2020},\n  doi={10.1000/example}\n}\n",
        encoding="utf-8",
    )
    (run_dir / "quality_review_round1.json").write_text(
        '{"p0_count":0,"delivery":"revise","floor_100":79.0,'
        '"review_loop":{"status":"round1_complete_revise_required","rounds":1,'
        '"reviewer_model":"codex-reviewer","fixer_model":"hermes","independent_reviewer":true,'
        '"floor_failed":true},'
        '"dimensions":{'
        '"academic_rigor":{"score":8.2},"novelty_positioning":{"score":8.0},'
        '"experimental_completeness":{"score":7.0},"writing_quality":{"score":8.6},'
        '"practical_feasibility":{"score":8.6},"citation_accuracy":{"score":7.0},'
        '"format_compliance":{"score":8.0}},'
        '"findings":[{"severity":"P1","location":"references.bib entry Hasan2020Diabetes",'
        '"issue":"out-of-domain citation retained",'
        '"concrete_fix":"Remove @Hasan2020Diabetes or replace it with a domain reference.",'
        '"rationale":"Avoid bibliography padding."}]}',
        encoding="utf-8",
    )
    (run_dir / "quality_review_log.md").write_text("round 1\n", encoding="utf-8")

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    review = result["gate_inputs"]["review"]
    assert review["delivery"] == "revise"
    assert review["review_loop"]["status"] == "repairs_applied_rereview_required"
    assert review["findings"] == []
    assert "Hasan2020Diabetes" not in (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "Hasan2020Diabetes" not in (run_dir / "references.bib").read_text(encoding="utf-8")
    assert "A retained domain sentence remains." in (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")


def test_review_heal_applies_structural_repair_and_normalizes_review_schema(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "references.bib").write_text(
        "@article{Bi_2023,\n  title={Pangu Weather},\n  year={2023}\n}\n",
        encoding="utf-8",
    )
    (run_dir / "claim_evidence_map.md").write_text(
        "| Claim | Evidence |\n|---|---|\n| Forecast error fell by 12%. | real_experiments/real_results.json |\n",
        encoding="utf-8",
    )
    for rel in ["paper_draft_v0.qmd", "paper_springer.qmd"]:
        (run_dir / rel).write_text(
            "---\ntitle: Test\nbibliography: references.bib\n---\n\n# Introduction\n\nForecast error fell by 12%.",
            encoding="utf-8",
        )
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps(
            {
                "p0_count": 0,
                "delivery": "pass",
                "floor_100": 86,
                "review_loop": {
                    "status": "done",
                    "rounds": 1,
                    "reviewer_model": "hermes-reviewer",
                    "fixer_model": "hermes-fixer",
                    "independent_reviewer": {"passed": True},
                    "floor_failed": False,
                },
                "dimensions": {
                    "academic_rigor": {"score": 86},
                    "novelty_positioning": {"score": 84},
                    "experimental_completeness": {"score": 82},
                    "writing_quality": {"score": 85},
                    "practical_feasibility": {"score": 87},
                    "citation_accuracy": {"score": 88},
                    "format_compliance": {"score": 86},
                },
                "findings": [],
            }
        ),
        encoding="utf-8",
    )

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    review = result["gate_inputs"]["review"]
    assert review["review_loop"]["independent_reviewer"] is True
    assert review["dimensions"]["academic_rigor"]["score"] == 8.6
    # Review-record schema normalization still runs on a pass verdict (the
    # record is not the manuscript), but manuscript files must stay untouched:
    # references.bib is hash-bound, and the pre-round-5 behavior of stuffing
    # abstract placeholders into a pass-reviewed bib invalidated the verdict.
    assert "abstract =" not in (run_dir / "references.bib").read_text(encoding="utf-8")
    assert "deterministic_review_schema_normalization" in (run_dir / "quality_review_log.md").read_text(encoding="utf-8")

    # On a revise verdict the manuscript-side deterministic repairs DO apply.
    review_data = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    review_data["delivery"] = "revise"
    review_data["p0_count"] = 1
    (run_dir / "quality_review_round1.json").write_text(json.dumps(review_data), encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    assert "abstract =" in (run_dir / "references.bib").read_text(encoding="utf-8")
    assert "V3.2 exact-match audit addendum" in (run_dir / "claim_evidence_map.md").read_text(encoding="utf-8")
    assert "link-citations: true" in (run_dir / "paper_springer.qmd").read_text(encoding="utf-8")


def test_review_heal_normalizes_alternate_dimension_score_schema(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps(
            {
                "p0_count": 0,
                "delivery": "pass",
                "overall_score_0_to_10": 8.2,
                "p0_findings": [],
                "review_loop": {
                    "status": "blocked_revise",
                    "rounds": 1,
                    "reviewer_model": "gpt-reviewer",
                    "fixer_model": "gpt-fixer",
                    "floor_failed": True,
                    "independent_reviewer": False,
                },
                "dimension_scores_0_to_10": [
                    {"dimension": "Academic rigor", "score": 8.0, "rationale": "ok"},
                    {"dimension": "Innovation and contribution positioning", "score": 7.8, "rationale": "ok"},
                    {"dimension": "Experimental completeness", "score": 7.4, "rationale": "ok"},
                    {"dimension": "Writing quality", "score": 8.4, "rationale": "ok"},
                    {"dimension": "Practical feasibility", "score": 8.1, "rationale": "ok"},
                    {"dimension": "Citation verification", "score": 9.3, "rationale": "ok"},
                    {"dimension": "Format and figure/table quality", "score": 8.6, "rationale": "ok"},
                ],
                "findings": [],
            }
        ),
        encoding="utf-8",
    )

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    review = result["gate_inputs"]["review"]
    assert review["p0_count"] == 0
    assert review["floor_100"] == 82.0
    assert review["review_loop"]["status"] == "blocked_revise"
    assert review["review_loop"]["independent_reviewer"] is False
    assert review["review_loop"]["floor_failed"] is True
    assert sorted(review["dimensions"]) == [
        "academic_rigor",
        "citation_accuracy",
        "experimental_completeness",
        "format_compliance",
        "novelty_positioning",
        "practical_feasibility",
        "writing_quality",
    ]
    assert review["dimensions"]["citation_accuracy"]["score"] == 9.3


def test_review_heal_backfills_diagnostic_revise_record_when_missing(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text("word " * 3100, encoding="utf-8")
    (run_dir / "claim_evidence_map.md").write_text("| Claim | Evidence |\n|---|---|\n", encoding="utf-8")
    (run_dir / "references.bib").write_text("@article{ref,title={Reference}}\n", encoding="utf-8")
    (run_dir / "doi_audit.json").write_text("{}", encoding="utf-8")
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text('{"reference_count": 40}', encoding="utf-8")

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    review = result["gate_inputs"]["review"]
    assert review["delivery"] == "revise"
    assert review["p0_count"] == 1
    assert review["floor_100"] < 80
    assert review["review_loop"]["independent_reviewer"] is False
    assert "diagnostic placeholder" in review["review_loop"]["reviewer_model"]
    assert review["dimensions"] == {}
    assert (run_dir / "quality_review_log.md").stat().st_size >= 200


def test_review_heal_invalidates_stale_incomplete_review_and_requires_rereview(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text("word " * 3100, encoding="utf-8")
    (run_dir / "claim_evidence_map.md").write_text("| Claim | Evidence |\n|---|---|\n| A | B |\n", encoding="utf-8")
    (run_dir / "references.bib").write_text("@article{ref,title={Reference}}\n", encoding="utf-8")
    (run_dir / "doi_audit.json").write_text("{}", encoding="utf-8")
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text('{"reference_count": 40}', encoding="utf-8")
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps(
            {
                "delivery": "revise",
                "floor_100": 72.0,
                "p0_count": 1,
                "review_loop": {"status": "blocked_revise", "independent_reviewer": False},
                "dimensions": {
                    "academic_rigor": {"score": 6.8},
                    "novelty_positioning": {"score": 6.5},
                    "experimental_completeness": {"score": 6.2},
                    "writing_quality": {"score": 6.8},
                    "practical_feasibility": {"score": 6.5},
                    "citation_accuracy": {"score": 6.5},
                    "format_compliance": {"score": 6.5},
                },
                "findings": [
                    {
                        "severity": "P0",
                        "issue": "Required manuscript artifacts are still incomplete.",
                        "rationale": "Review fallback cannot pass incomplete declared artifacts.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    review = result["gate_inputs"]["review"]
    assert review["delivery"] == "revise"
    assert review["p0_count"] == 1
    assert "stale" in json.dumps(review["findings"]).lower()
    assert review["review_loop"]["independent_reviewer"] is False


def test_review_heal_materializes_missing_claim_evidence_map_before_review(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text("word " * 3100, encoding="utf-8")
    (run_dir / "references.bib").write_text("@article{ref,title={Reference}}\n", encoding="utf-8")
    (run_dir / "doi_audit.json").write_text("{}", encoding="utf-8")
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text('{"reference_count": 40}', encoding="utf-8")

    result = paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    review = result["gate_inputs"]["review"]
    assert (run_dir / "claim_evidence_map.md").is_file()
    assert review["delivery"] == "revise"
    assert review["p0_count"] == 1


def test_bounded_golden_pipeline_runs_selected_gates_through_v3(tmp_path: Path, golden_dir: Path):
    run_dir = tmp_path / "run"

    def fixture_runner(command: list[str], cwd: Path, _timeout_s: int):
        prompt = command[-1]
        for rel in BOUNDED_GOLDEN_OUTPUTS:
            if rel not in prompt:
                continue
            src = golden_dir / rel
            dst = cwd / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
        return CliRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    orchestrator = EngineV3Orchestrator(
        runtime=CodexCliRuntime(runner=fixture_runner),
        domain_pack=PaperPack(),
        phases=bounded_golden_pipeline(),
        dossier_store=DossierStore(run_dir),
    )

    dossier = orchestrator.run(job_id="golden-1", resume=False)
    loaded = DossierStore(run_dir).load()

    assert dossier.phases == {"data": "done", "render_gates": "done"}
    assert loaded.phases == dossier.phases
    assert [r["phase"] for r in dossier.gate_reports] == ["data", "render_gates"]
    assert all(report["blocked"] is False for report in dossier.gate_reports)
    assert [d["phase"] for d in dossier.delegations] == ["data", "render_gates"]
    assert dossier.artifacts["references.bib"].sha256
    assert dossier.artifacts["paper_draft_v0.qmd"].sha256


def test_full_paper_pipeline_runs_all_phases_and_delivery_gate(
    tmp_path: Path,
    golden_dir: Path,
    monkeypatch,
):
    run_dir = tmp_path / "run"
    clean_draft = _clean_long_draft()

    def fake_format_repair(run_dir: Path, _contract: dict):
        (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
        return {"crossref_ok": True}

    monkeypatch.setattr(paper_pipeline.format_repair, "verify_and_repair", fake_format_repair)
    monkeypatch.setattr(
        paper_pipeline,
        "_validate_delivery_pdf",
        lambda _pdf, _run_dir=None: {
            "valid": True,
            "producer": "xdvipdfmx",
            "raw_citation_count": 0,
            "unresolved_marker_count": 0,
            "numbered_section_detected": True,
            "table_widths": {"valid": True, "findings": []},
            "findings": [],
        },
    )

    def full_runner(command: list[str], cwd: Path, _timeout_s: int):
        prompt = command[-1]
        for rel in DATA_OUTPUTS:
            if rel in prompt:
                src = golden_dir / rel
                dst = cwd / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)
        if "phase3_positioning.md" in prompt:
            (cwd / "phase3_positioning.md").write_text("## Gap\nBounded gap.\n", encoding="utf-8")
        if "phase4_structure.md" in prompt:
            (cwd / "phase4_structure.md").write_text("## Structure\nIMRaD.\n", encoding="utf-8")
        if "claim_evidence_map.md" in prompt:
            (cwd / "claim_evidence_map.md").write_text(
                "| Claim | Evidence |\n"
                "|---|---|\n"
                "| k = 8; SMD -0.4327; I-squared 95.4 | real_results meta pooled |\n",
                encoding="utf-8",
            )
        if "paper_draft_v0.qmd" in prompt:
            for rel in [p for p in FULL_PIPELINE_OUTPUTS if p.startswith("sections/")]:
                path = cwd / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("section\n", encoding="utf-8")
            (cwd / "paper_draft_v0.qmd").write_text(clean_draft, encoding="utf-8")
        if "paper_springer.qmd" in prompt:
            (cwd / "paper_springer.qmd").write_text(clean_draft, encoding="utf-8")
        if "quality_review_round1.json" in prompt:
            (cwd / "quality_review_round1.json").write_text(
                '{"p0_count": 0, "delivery": "pass", "floor_100": 82.0, '
                '"review_method": {"schema_version": "paperlab.review_method.v3.2", '
                '"decision_owner": "hermes", "capability_class": "domain_expert_review", '
                '"selected_skill": "paper-review-skill", '
                '"selection_reason": "domain expert review before delivery", '
                '"vip_capability_required": true, "vip_capability_available": true, '
                '"inputs_checked": ["paper_draft_v0.qmd", "references.bib"]}, '
                '"review_loop": {"status": "passed", "rounds": 1, '
                '"reviewer_model": "codex-class", "fixer_model": "big-pickle", '
                '"independent_reviewer": true, "floor_failed": false}, '
                '"dimensions": {'
                '"academic_rigor": {"score": 8.1}, '
                '"novelty_positioning": {"score": 8.4}, '
                '"experimental_completeness": {"score": 7.8}, '
                '"writing_quality": {"score": 8.3}, '
                '"practical_feasibility": {"score": 8.0}, '
                '"citation_accuracy": {"score": 8.6}, '
                '"format_compliance": {"score": 8.5}}}\n',
                encoding="utf-8",
            )
        if "quality_review_log.md" in prompt:
            (cwd / "quality_review_log.md").write_text(
                "# Quality review log\n\n## Skill Decision Trace\n\n"
                "- visible: paper-review-skill, elite-reviewer-audit\n"
                "- selected: paper-review-skill because the task needs a domain expert review\n"
                "- inputs checked: paper_draft_v0.qmd, references.bib\n\n"
                "- round 1: passed; no P0; floor ok\n",
                encoding="utf-8",
            )
        return CliRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    dossier = EngineV3Orchestrator(
        runtime=CodexCliRuntime(runner=full_runner),
        domain_pack=PaperPack(),
        phases=full_paper_pipeline(),
        dossier_store=DossierStore(run_dir),
    ).run(job_id="full-1", resume=False)

    assert dossier.phases == {
        "data": "done",
        "gap": "done",
        "structure": "done",
        "write": "done",
        "claim_evidence": "done",
        "render_gates": "done",
        "review_heal": "done",
        "format_repair": "done",
    }
    assert [report["failed_blocks"] for report in dossier.gate_reports] == [
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    ]
    assert [result["gate_id"] for report in dossier.gate_reports for result in report["results"]] == [
        "A",
        "E",
        "G",
        "B",
        "C",
        "D",
        "F",
        "R",
        "Z",
    ]
    assert dossier.artifacts["paper_draft_v0.pdf"].sha256


def test_claim_evidence_phase_has_gate_b_repair_budget():
    phases = {phase.id: phase for phase in full_paper_pipeline()}

    claim_evidence = phases["claim_evidence"]

    assert claim_evidence.gate_ids == ["B"]
    assert claim_evidence.max_repair_attempts == 3
    assert "flagged Gate B claim" in claim_evidence.repair_prompt
    assert "Do not return unchanged files" in claim_evidence.repair_prompt
    assert "claim_evidence_map.md" in claim_evidence.expected_outputs
    assert "paper_draft_v0.qmd" not in claim_evidence.expected_outputs
    assert "paper_draft_v0.qmd" in claim_evidence.repair_expected_outputs
    assert "sections/introduction.md" in claim_evidence.repair_expected_outputs


def test_claim_evidence_handler_augments_traceable_numeric_claims(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text(
        "In the M4 adjusted model, the current-DTP3 row reports a coefficient of "
        "-0.234 (clustered SE 0.059, 95% CI [-0.350, -0.118], p = 7.618e-05).",
        encoding="utf-8",
    )
    (run_dir / "claim_evidence_map.md").write_text(
        "| Claim | Evidence |\n|---|---|\n",
        encoding="utf-8",
    )
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text(
        '{"current_coef": -0.234, "current_se": 0.059, '
        '"current_ci": [-0.350, -0.118], "current_p": 7.618e-05}',
        encoding="utf-8",
    )

    changed = paper_pipeline._augment_traceable_claim_evidence_rows(run_dir)

    assert changed is True
    text = (run_dir / "claim_evidence_map.md").read_text(encoding="utf-8")
    assert "current-DTP3 row reports a coefficient of -0.234" in text
    assert "7.618e-05" in text

    from framework import run_gates
    from packs.paper import PaperPack

    report = run_gates(PaperPack(), paper_pipeline.paperctl._build_dossier(run_dir), only={"B"})
    assert report.blocked is False


def test_write_phase_repairs_missing_declared_outputs():
    phases = {phase.id: phase for phase in full_paper_pipeline()}

    write = phases["write"]

    assert write.max_repair_attempts == 2
    assert "missing manuscript outputs" in write.repair_prompt
    assert write.repair_expected_outputs == WRITE_OUTPUTS


def test_write_phase_runtime_missing_outputs_gets_repair_attempt(tmp_path: Path):
    run_dir = tmp_path / "run"
    calls: list[str] = []

    def runner(command: list[str], cwd: Path, _timeout_s: int):
        prompt = command[-1]
        calls.append(prompt)
        if "Repair attempt: 1" in prompt:
            for rel in WRITE_OUTPUTS:
                path = cwd / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("repaired\n", encoding="utf-8")
        return CliRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    write_phase = {phase.id: phase for phase in full_paper_pipeline()}["write"]
    dossier = EngineV3Orchestrator(
        runtime=CodexCliRuntime(runner=runner),
        domain_pack=PaperPack(),
        phases=[write_phase],
        dossier_store=DossierStore(run_dir),
    ).run(job_id="write-repair-1", resume=False)

    assert dossier.phases == {"write": "done"}
    assert [delegation["task_id"] for delegation in dossier.delegations] == [
        "write:brain",
        "write:repair:1",
    ]
    assert "missing declared output: paper_draft_v0.qmd" in dossier.delegations[0]["blockers"]
    assert (run_dir / "paper_draft_v0.qmd").is_file()
    assert any("Repair the write phase missing manuscript outputs" in prompt for prompt in calls)


def test_review_heal_phase_requires_fresh_review_artifacts_before_manuscript_repairs():
    phases = {phase.id: phase for phase in full_paper_pipeline()}

    review_heal = phases["review_heal"]

    assert "quality_review_round1.json" in review_heal.expected_outputs
    assert "quality_review_log.md" in review_heal.expected_outputs
    assert "paper_draft_v0.qmd" in review_heal.expected_outputs
    assert "paper_springer.qmd" in review_heal.expected_outputs
    assert "sections/results.md" in review_heal.expected_outputs
    assert "figures/fig_prisma_flow.png" in review_heal.expected_outputs
    assert review_heal.repair_expected_outputs is not None
    assert review_heal.repair_expected_outputs == review_heal.expected_outputs
    assert "Do not treat manuscript edits alone as completion" in review_heal.prompt
    assert "dimensions" in review_heal.prompt
    assert "academic_rigor" in review_heal.prompt
    assert "concrete_fix" in review_heal.prompt
    assert "legacy v2 audit artifacts" in review_heal.prompt
    assert "must not fail delivery solely because they are absent" in review_heal.prompt
    assert "bounded final re-review" in review_heal.repair_prompt
    assert "You may edit manuscript/source/figure artifacts" in review_heal.repair_prompt


def test_table_width_validation_requires_tbl_colwidths(tmp_path: Path):
    qmd = tmp_path / "paper_springer.qmd"
    qmd.write_text(
        "| Method | Long text result | Score | Notes | Risk |\n"
        "|---|---|---|---|---|\n"
        "| A | long prose | 0.5 | note | risk |\n\n"
        ': Main Results {#tbl-main}\n',
        encoding="utf-8",
    )

    invalid = _validate_table_widths(tmp_path)

    assert invalid["valid"] is False
    assert invalid["findings"] == [
        "table main missing tbl-colwidths",
        "paper requires at least 2 real Quarto tables; found 1",
    ]

    qmd.write_text(
        "| Method | Long text result | Score | Notes | Risk |\n"
        "|---|---|---|---|---|\n"
        "| A | long prose | 0.5 | note | risk |\n\n"
        ': Main Results {#tbl-main tbl-colwidths="[25,25,15,20,15]"}\n',
        encoding="utf-8",
    )

    one_table = _validate_table_widths(tmp_path)

    assert one_table["valid"] is False
    assert one_table["findings"] == ["paper requires at least 2 real Quarto tables; found 1"]

    qmd.write_text(
        "| Method | Long text result | Score | Notes | Risk |\n"
        "|---|---|---|---|---|\n"
        "| A | long prose | 0.5 | note | risk |\n\n"
        ': Main Results {#tbl-main tbl-colwidths="[25,25,15,20,15]"}\n\n'
        "| Ablation | Result |\n"
        "|---|---|\n"
        "| no evidence repair | lower consistency |\n\n"
        ': Ablation Results {#tbl-ablation tbl-colwidths="[35,65]"}\n',
        encoding="utf-8",
    )

    valid = _validate_table_widths(tmp_path)

    assert valid["valid"] is True
    assert [table["sum"] for table in valid["tables"]] == [100, 100]


def test_table_layout_validation_fails_without_rendered_qmd(tmp_path: Path):
    result = _validate_table_widths(tmp_path)

    assert result["valid"] is False
    assert result["findings"] == ["paper_springer.qmd missing; cannot validate table layout"]


def test_delivery_pdf_validation_blocks_raw_citations_and_missing_section_numbers(
    tmp_path: Path,
    monkeypatch,
):
    pdf = tmp_path / "paper_draft_v0.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
    _write_two_valid_tables(tmp_path)

    def fake_run_text(command: list[str], *, timeout_s: int) -> str:
        if command[0] == "pdfinfo":
            return "Producer: xdvipdfmx\nCreator: LaTeX with hyperref\n"
        if command[0] == "pdftotext":
            return "Introduction\nPangu-Weather improved forecasts [@Bi_2023].\nMethods\n"
        return ""

    monkeypatch.setattr(paper_pipeline, "_run_text", fake_run_text)

    result = _validate_delivery_pdf(pdf, tmp_path)

    assert result["valid"] is False
    assert result["raw_citation_count"] == 1
    assert result["numbered_section_detected"] is False
    assert "PDF contains raw Pandoc citation tokens" in result["findings"]
    assert "PDF has no detected numbered section headings" in result["findings"]


def test_delivery_pdf_validation_blocks_template_boilerplate_bad_citations_and_duplicate_addenda(
    tmp_path: Path,
    monkeypatch,
):
    pdf = tmp_path / "paper_draft_v0.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
    _write_two_valid_tables(tmp_path)

    bad_text = "\n".join(
        [
            "1. Introduction",
            "For V3.2 production quality, this section keeps the argument explicit.",
            "For V3.2 production quality, this section keeps the argument explicit.",
            "The section is intentionally written as an auditable bridge between the research contract and the available artifacts.",
            "The section is intentionally written as an auditable bridge between the research contract and the available artifacts.",
            "The evidence base is described here. (See, a,b,c)",
            "9. V3.2 Traceability and Claim Discipline Addendum",
            "10. V3.2 Traceability and Claim Discipline Addendum",
            "11. Traceability Tables",
            "12. Traceability Tables",
        ]
    )

    def fake_run_text(command: list[str], *, timeout_s: int) -> str:
        if command[0] == "pdfinfo":
            return "Producer: xdvipdfmx\nCreator: LaTeX with hyperref\n"
        if command[0] == "pdftotext":
            return bad_text
        return ""

    monkeypatch.setattr(paper_pipeline, "_run_text", fake_run_text)

    result = _validate_delivery_pdf(pdf, tmp_path)

    assert result["valid"] is False
    assert "PDF contains repeated fallback boilerplate" in result["findings"]
    assert "PDF contains low-quality citation labels" in result["findings"]
    assert "PDF contains duplicated traceability addenda or tables" in result["findings"]


def test_render_cleanup_removes_repeated_fallback_boilerplate_and_duplicate_addenda(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    repeated = "\n\n".join(
        [
            "---\ntitle: Test\n---",
            "## Introduction",
            "For V3.2 production quality, this section keeps the argument explicit, avoids unsupported causal language, and leaves a clear path for claim-evidence auditing.",
            "The section is intentionally written as an auditable bridge between the research contract and the available artifacts. It identifies what the run can support, what remains outside the evidence boundary, and how later review should verify each statement against references.bib, doi_audit.json, real_results.json, generated figures, and the claim-evidence map.",
            "Domain-specific paragraph.",
            "## V3.2 Traceability and Claim Discipline Addendum",
            "Generated note one.",
            "## V3.2 Traceability and Claim Discipline Addendum",
            "Generated note two.",
            "## Traceability Tables",
            "| A | B |\n|---|---|\n| x | y |\n\n: Artifact Traceability {#tbl-artifact-traceability tbl-colwidths=\"[50,50]\"}",
            "## Traceability Tables",
            "| A | B |\n|---|---|\n| x | y |\n\n: Artifact Traceability {#tbl-artifact-traceability-2 tbl-colwidths=\"[50,50]\"}",
        ]
    )
    for rel in ("paper_draft_v0.qmd", "paper_springer.qmd"):
        (run_dir / rel).write_text(repeated, encoding="utf-8")

    changed = paper_pipeline._repair_generated_content_quality_v3_2(run_dir)

    assert changed is True
    text = (run_dir / "paper_springer.qmd").read_text(encoding="utf-8")
    assert "For V3.2 production quality" not in text
    assert "auditable bridge between the research contract" not in text
    assert text.count("## V3.2 Traceability and Claim Discipline Addendum") <= 1
    assert text.count("## Traceability Tables") <= 1


def test_render_cleanup_removes_citations_without_author_year_metadata(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "references.bib").write_text(
        "@article{bad,title={DOI only},doi={10.1000/bad}}\n"
        "@article{good,title={Good},author={Lee, A.},year={2024}}\n",
        encoding="utf-8",
    )
    for rel in ("paper_draft_v0.qmd", "paper_springer.qmd"):
        (run_dir / rel).write_text(
            "## Introduction\n\nEvidence-only sentence [@bad; @good]. DOI-only sentence [@bad].",
            encoding="utf-8",
        )

    changed = paper_pipeline._repair_generated_content_quality_v3_2(run_dir)

    assert changed is True
    text = (run_dir / "paper_springer.qmd").read_text(encoding="utf-8")
    assert "[@bad" not in text
    assert "[@good]" in text


def test_fallback_writer_never_synthesizes_boilerplate(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "research_contract.json").write_text(
        json.dumps({"topic": "DTP3 coverage and mortality"}), encoding="utf-8"
    )
    (run_dir / "references.bib").write_text(
        "@article{good,title={Good Reference},author={Lee, A.},year={2023}}\n",
        encoding="utf-8",
    )

    changed = paper_pipeline._ensure_write_outputs_v3_2(run_dir)

    assert changed is False
    assert not (run_dir / "paper_draft_v0.qmd").is_file()


def test_delivery_pdf_validation_accepts_resolved_citations_numbering_and_table_widths(
    tmp_path: Path,
    monkeypatch,
):
    pdf = tmp_path / "paper_draft_v0.pdf"
    pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
    _write_two_valid_tables(tmp_path)

    def fake_run_text(command: list[str], *, timeout_s: int) -> str:
        if command[0] == "pdfinfo":
            return "Producer: xdvipdfmx\nCreator: LaTeX with hyperref\n"
        if command[0] == "pdftotext":
            return "1. Introduction\nPangu-Weather improved forecasts (Bi et al. 2023).\n2. Methods\n"
        return ""

    monkeypatch.setattr(paper_pipeline, "_run_text", fake_run_text)

    result = _validate_delivery_pdf(pdf, tmp_path)

    assert result["valid"] is True
    assert result["raw_citation_count"] == 0
    assert result["unresolved_marker_count"] == 0
    assert result["numbered_section_detected"] is True
    assert result["table_widths"]["valid"] is True


def _clean_long_draft() -> str:
    sentence = (
        "The SMD pool included k = 8 effects [@geng2026; @yan2026]. "
        "The pooled standardised mean difference was -0.4327, which indicates a reduction "
        "in depressive symptoms favouring exercise [@lan2025]. "
        "Heterogeneity was considerable, with I-squared of 95.4, and this is consistent "
        "with a diverse study pool spanning different exercise modalities [@tu2025]. "
        "The pooled estimate is directionally informative rather than clinically definitive."
    )
    return "\n\n".join([sentence for _ in range(90)])


def _write_two_valid_tables(run_dir: Path) -> None:
    (run_dir / "paper_springer.qmd").write_text(
        "| Method | Long text result | Score | Notes | Risk |\n"
        "|---|---|---|---|---|\n"
        "| A | long prose | 0.5 | note | risk |\n\n"
        ': Main Results {#tbl-main tbl-colwidths="[25,25,15,20,15]"}\n\n'
        "| Ablation | Result |\n"
        "|---|---|\n"
        "| no evidence repair | lower consistency |\n\n"
        ': Ablation Results {#tbl-ablation tbl-colwidths="[35,65]"}\n',
        encoding="utf-8",
    )


def test_render_log_overfull_hbox_blocks_delivery(tmp_path: Path):
    """2026-07-02 mindfulness PDF shipped Table 1 with the long artifact
    filename overflowing into the neighbor column. The renderer had already
    reported it (Overfull \\hbox in paper_springer.log) - the gate must consume
    that ground truth instead of trusting declared tbl-colwidths."""
    from engine_v3.pipelines.paper import _validate_render_log_overflow

    log = tmp_path / "paper_springer.log"
    log.write_text(
        "some latex noise\n"
        "Overfull \\hbox (23.13pt too wide) in paragraph at lines 210--214\n"
        "more noise\n"
        "Overfull \\hbox (1.2pt too wide) in paragraph at lines 300--301\n",
        encoding="utf-8",
    )

    result = _validate_render_log_overflow(tmp_path)

    # 23pt is a visible overlap -> finding; 1.2pt is ordinary TeX noise -> ignored
    assert result["valid"] is False
    assert result["overfull_count"] == 1
    assert any("Overfull" in f for f in result["findings"])


def test_render_log_overflow_passes_on_clean_or_minor_log(tmp_path: Path):
    from engine_v3.pipelines.paper import _validate_render_log_overflow

    (tmp_path / "paper_springer.log").write_text(
        "Overfull \\hbox (2.9pt too wide) detected\n", encoding="utf-8"
    )
    assert _validate_render_log_overflow(tmp_path)["valid"] is True

    (tmp_path / "paper_springer.log").unlink()
    missing = _validate_render_log_overflow(tmp_path)
    assert missing["valid"] is True
    assert missing["log_present"] is False


def test_caption_claims_must_match_poolability(tmp_path: Path):
    """Figure 4's caption claimed 'effect sizes and the random-effects pooled
    estimate' on a run whose real_results said poolable_k=0. Caption text is
    claim surface; it must obey claim<=evidence like body prose."""
    from engine_v3.pipelines.paper import _validate_caption_claims

    (tmp_path / "paper_draft_v0.qmd").write_text(
        "---\ntitle: x\n---\n\n"
        "![Forest plot of study-level effect sizes and the random-effects pooled estimate.](figures/fig_forest_plot.png){#fig-forest}\n\n"
        "![PRISMA-style flow diagram of study selection.](figures/fig_prisma_flow.png){#fig-prisma}\n",
        encoding="utf-8",
    )
    (tmp_path / "real_experiments").mkdir()
    (tmp_path / "real_experiments" / "real_results.json").write_text(
        '{"max_poolable_k": 0, "synthesis": {"numeric_effect_count": 0}}',
        encoding="utf-8",
    )

    result = _validate_caption_claims(tmp_path)

    assert result["valid"] is False
    assert any("pooled estimate" in f or "effect size" in f for f in result["findings"])
    # the honest PRISMA caption must not be flagged
    assert not any("PRISMA" in f for f in result["findings"])


def test_caption_claims_allowed_when_effects_exist(tmp_path: Path):
    from engine_v3.pipelines.paper import _validate_caption_claims

    (tmp_path / "paper_draft_v0.qmd").write_text(
        "![Forest plot of pooled effect sizes.](figures/fig_forest_plot.png){#fig-forest}\n",
        encoding="utf-8",
    )
    (tmp_path / "real_experiments").mkdir()
    (tmp_path / "real_experiments" / "real_results.json").write_text(
        '{"max_poolable_k": 8, "synthesis": {"numeric_effect_count": 8}}',
        encoding="utf-8",
    )

    assert _validate_caption_claims(tmp_path)["valid"] is True


def test_title_language_must_match_body_language(tmp_path: Path):
    """The mindfulness PDF shipped a Chinese title on an all-English
    manuscript (title copied verbatim from the b-side contract topic)."""
    from engine_v3.pipelines.paper import _validate_title_language

    (tmp_path / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "校園正念介入對青少年憂鬱與焦慮的效果量"\n---\n\n'
        "## Introduction\n\n"
        + ("This is an English manuscript body about mindfulness. " * 40),
        encoding="utf-8",
    )

    result = _validate_title_language(tmp_path)

    assert result["valid"] is False
    assert any("language" in f.lower() for f in result["findings"])


def test_title_language_consistent_passes(tmp_path: Path):
    from engine_v3.pipelines.paper import _validate_title_language

    (tmp_path / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "School Mindfulness and Adolescent Outcomes"\n---\n\n'
        + ("English body text here. " * 40),
        encoding="utf-8",
    )
    assert _validate_title_language(tmp_path)["valid"] is True

    (tmp_path / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "校園正念介入研究"\n---\n\n' + ("這是中文正文內容，全文以中文撰寫的研究論文草稿。" * 40),
        encoding="utf-8",
    )
    assert _validate_title_language(tmp_path)["valid"] is True


def test_inline_heading_leakage_is_a_content_finding(tmp_path: Path):
    """v3_0f6a0c83f9cf shipped '## Related Work', '## Methods', '## Results',
    '## Discussion', '## Limitations', '## Conclusion' as literal text stuck
    mid-paragraph in the rendered PDF - the composed qmd concatenated section
    headings onto paragraph lines, so no section after Introduction existed
    as a real heading. Both mechanical gates and the Hermes review (floor 84,
    0 findings) missed it; a human caught it on page 3."""
    from engine_v3.pipelines.paper import _validate_inline_heading_leakage

    (tmp_path / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "T"\n---\n\n'
        "# Introduction\n\n"
        "The evidence blocks stronger conclusions. ## Related Work\n\n"
        "More prose here that ends a section. ## Methods\n",
        encoding="utf-8",
    )

    result = _validate_inline_heading_leakage(tmp_path)

    assert result["valid"] is False
    joined = " ".join(result["findings"]).lower()
    assert "related work" in joined or "heading" in joined


def test_headings_on_their_own_lines_pass(tmp_path: Path):
    from engine_v3.pipelines.paper import _validate_inline_heading_leakage

    (tmp_path / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "T"\n---\n\n'
        "# Introduction\n\nProse.\n\n"
        "## Related Work\n\nProse citing C## notation and a## variable.\n\n"
        "## Methods\n\nProse.\n",
        encoding="utf-8",
    )

    assert _validate_inline_heading_leakage(tmp_path)["valid"] is True


def test_zero_rendered_citations_is_a_content_finding(tmp_path: Path):
    """v3_0f6a0c83f9cf shipped an EMPTY References section and zero inline
    citations while 35 two-source-verified bib entries sat unused - the body
    named authors in prose without a single @citekey, so citeproc rendered
    nothing. The citation-distribution validator only guarded against dump
    patterns, not against total absence."""
    from engine_v3.pipelines.paper import _validate_citations_rendered

    (tmp_path / "references.bib").write_text(
        "@article{zhang2020,title={A},year={2020}}\n"
        "@article{lee2021,title={B},year={2021}}\n",
        encoding="utf-8",
    )
    (tmp_path / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "T"\n---\n\n'
        "# Introduction\n\nZhang, Zhou, and Jiang proposed a kink design. "
        "No citation markers appear anywhere in this manuscript.\n",
        encoding="utf-8",
    )

    result = _validate_citations_rendered(tmp_path)

    assert result["valid"] is False
    assert any("citation" in f.lower() for f in result["findings"])


def test_cited_manuscript_passes_citations_rendered(tmp_path: Path):
    from engine_v3.pipelines.paper import _validate_citations_rendered

    (tmp_path / "references.bib").write_text(
        "@article{zhang2020,title={A},year={2020}}\n",
        encoding="utf-8",
    )
    (tmp_path / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "T"\n---\n\nA kink design was proposed [@zhang2020].\n',
        encoding="utf-8",
    )

    assert _validate_citations_rendered(tmp_path)["valid"] is True


def test_new_validators_registered_in_content_validators(tmp_path: Path):
    from engine_v3.pipelines.paper import (
        content_validators,
        _validate_citations_rendered,
        _validate_inline_heading_leakage,
    )

    registered = content_validators()
    assert _validate_inline_heading_leakage in registered
    assert _validate_citations_rendered in registered


def test_caption_gate_allows_negated_honest_statements(tmp_path: Path):
    """Round 3 false positive: the repaired honest caption 'Outcome-domain
    pooling status ... 0 extracted effect sizes' was flagged because it
    contains the token 'effect size'. Negated/deferred statements are honest
    disclosures, not claims."""
    from engine_v3.pipelines.paper import _validate_caption_claims

    (tmp_path / "paper_draft_v0.qmd").write_text(
        "![Outcome-domain pooling status: 0 extracted effect sizes; pooling deferred, not estimated.](figures/fig_forest_plot.png){#fig-forest}\n",
        encoding="utf-8",
    )
    (tmp_path / "real_experiments").mkdir()
    (tmp_path / "real_experiments" / "real_results.json").write_text(
        '{"max_poolable_k": 0, "synthesis": {"numeric_effect_count": 0}}',
        encoding="utf-8",
    )

    assert _validate_caption_claims(tmp_path)["valid"] is True


def test_caption_gate_scans_sections_for_reinfiltration(tmp_path: Path):
    """Round 5: the fabricated caption fixed in paper_draft_v0.qmd came BACK
    because sections/results.md still carried it and Hermes recomposed from
    sections. The gate must scan every manuscript source and name the file,
    so the repair prompt tells Hermes exactly where to fix."""
    from engine_v3.pipelines.paper import _validate_caption_claims

    (tmp_path / "paper_draft_v0.qmd").write_text(
        "![Outcome-domain pooling status: 0 extracted effect sizes, not pooled.](figures/fig_forest_plot.png){#fig-forest}\n",
        encoding="utf-8",
    )
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections" / "results.md").write_text(
        "![Forest plot of study-level effect sizes and the random-effects pooled estimate.](figures/fig_forest_plot.png){#fig-forest}\n",
        encoding="utf-8",
    )
    (tmp_path / "real_experiments").mkdir()
    (tmp_path / "real_experiments" / "real_results.json").write_text(
        '{"max_poolable_k": 0, "synthesis": {"numeric_effect_count": 0}}',
        encoding="utf-8",
    )

    result = _validate_caption_claims(tmp_path)

    assert result["valid"] is False
    assert any("sections/results.md" in f for f in result["findings"])


def test_review_heal_surfaces_pending_content_findings_to_hermes(tmp_path: Path):
    """Round 6: review passed but the flagged caption survived because the
    gate's findings never reached the reviewer. The review_heal collection now
    writes pending_content_findings.md (deterministic ground truth) so the
    prompt puts the exact blockers on Hermes's worklist."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "English Title"\n---\n\n'
        "![Forest plot of pooled effect sizes.](figures/fig_forest_plot.png){#fig-forest}\n\n"
        + ("English body. " * 50),
        encoding="utf-8",
    )
    (run_dir / "real_experiments").mkdir()
    (run_dir / "real_experiments" / "real_results.json").write_text(
        '{"max_poolable_k": 0, "synthesis": {"numeric_effect_count": 0}}',
        encoding="utf-8",
    )

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    pending = (run_dir / "pending_content_findings.md").read_text(encoding="utf-8")
    assert "pooled effect" in pending or "effect size" in pending
    assert "paper_draft_v0.qmd" in pending


def test_pending_content_findings_removed_when_clean(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "English Title"\n---\n\n' + ("English body. " * 50),
        encoding="utf-8",
    )
    (run_dir / "pending_content_findings.md").write_text("stale", encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    assert not (run_dir / "pending_content_findings.md").is_file()


def test_review_prompts_reference_pending_content_findings():
    from engine_v3.pipelines.paper import REVIEW_HEAL_PROMPT, REVIEW_HEAL_REPAIR_PROMPT

    for prompt in (REVIEW_HEAL_PROMPT, REVIEW_HEAL_REPAIR_PROMPT):
        assert "pending_content_findings.md" in prompt
        assert "deterministic" in prompt.lower()


def test_review_prompts_pin_independent_reviewer_semantics():
    """Round 18: a fully passing review (floor 80, p0=0, provenance ok) was
    blocked solely because Hermes interpreted review_loop.independent_reviewer
    as 'a different model reviewed' and honestly wrote false. Same failure
    family as the 'passed_after_repair' vocabulary drift (round 11): a gate-
    consumed field whose semantics the prompt never pinned. The prompts must
    define the canonical meaning: a dedicated final review pass over the
    finished manuscript after all repairs — not a different model."""
    from engine_v3.pipelines.paper import REVIEW_HEAL_PROMPT, REVIEW_HEAL_REPAIR_PROMPT

    for prompt in (REVIEW_HEAL_PROMPT, REVIEW_HEAL_REPAIR_PROMPT):
        assert "independent_reviewer" in prompt
        lowered = " ".join(prompt.lower().split())
        assert "dedicated final review pass" in lowered
        assert "does not mean a different model" in lowered


def test_review_heal_removes_stale_pdf_so_reviewer_audits_sources(tmp_path: Path):
    """Round 8 chicken-and-egg: manuscript sources were clean but the reviewer
    read the PREVIOUS round's rendered PDF (with the old caption) and issued a
    P0 revise, so the run never reached format_repair which would have
    re-rendered it. The stale PDF is definitionally outdated during
    review_heal; remove it so the reviewer audits sources only."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text(
        '---\ntitle: "English Title"\n---\n\n' + ("English body. " * 50),
        encoding="utf-8",
    )
    (run_dir / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4 stale render")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="review_heal", task_id="review_heal:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    assert not (run_dir / "paper_draft_v0.pdf").is_file()


def test_paper_gate_plugin_uses_v3_requirements_on_v3_runs(tmp_path: Path):
    """Round 10: the hermes paper_gate plugin blocked the reviewer's render on
    a V3.2 run by demanding v2 legacy audit artifacts, which surfaced as an
    unresolvable P0. On a v3 run (dossier.v3.json present) only the v3
    prerequisites apply."""
    import paper_gate

    (tmp_path / "dossier.v3.json").write_text("{}", encoding="utf-8")
    (tmp_path / "claim_evidence_map.md").write_text("| C | E |\n", encoding="utf-8")
    (tmp_path / "references.bib").write_text("@article{a,title={A}}\n", encoding="utf-8")
    (tmp_path / "quality_review_log.md").write_text("# log\n", encoding="utf-8")

    result = paper_gate._pre_tool_call(
        tool_name="terminal",
        args={"command": "quarto render paper_springer.qmd", "workdir": str(tmp_path)},
    )
    assert result is None

    # v2 run (research_contract.json, no dossier.v3.json): legacy
    # requirements still enforced
    v2_dir = tmp_path / "v2"
    v2_dir.mkdir()
    (v2_dir / "research_contract.json").write_text("{}", encoding="utf-8")
    blocked = paper_gate._pre_tool_call(
        tool_name="terminal",
        args={"command": "quarto render paper.qmd", "workdir": str(v2_dir)},
    )
    assert blocked is not None and blocked["action"] == "block"


def test_paper_gate_plugin_ignores_scratch_render_dirs(tmp_path: Path):
    """Batch job v3_03d8e9b50bfc: the reviewer copied sources to
    /tmp/review_heal17_render for a visual page inspection; that scratch dir
    has no dossier.v3.json, so the plugin fell back to V2 requirements and
    blocked the render - which the reviewer honestly reported as a phantom
    'Phase 9 gate/audit artifacts missing' P0, re-blocking the job every
    round. A directory with NO paper-run markers (neither dossier.v3.json
    nor research_contract.json) is not a delivery target; do not gate it."""
    import paper_gate

    scratch = tmp_path / "scratch_render"
    scratch.mkdir()
    (scratch / "paper_draft_v0.qmd").write_text("copy", encoding="utf-8")
    (scratch / "references.bib").write_text("@article{a,title={A}}\n", encoding="utf-8")

    result = paper_gate._pre_tool_call(
        tool_name="terminal",
        args={"command": "quarto render paper_draft_v0.qmd", "workdir": str(scratch)},
    )
    assert result is None


def test_stamp_refreshes_when_review_is_newer_than_manuscript(tmp_path: Path):
    """Round 13: Hermes repaired the manuscript and rewrote the review in the
    same attempt, but copied the previous stamp into review_method; the
    stamp-once logic kept the stale hash and Gate R blocked a legitimate
    fresh review. If the review file is newer than every manuscript source,
    it reviewed the current state - re-stamp faithfully."""
    import os, time

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "paper_draft_v0.qmd").write_text("repaired manuscript", encoding="utf-8")
    old = time.time() - 100
    os.utime(run_dir / "paper_draft_v0.qmd", (old, old))
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps(
            {
                "delivery": "pass",
                "review_method": {
                    "decision_owner": "hermes",
                    "reviewed_manuscript_sha256": "0" * 64,
                },
            }
        ),
        encoding="utf-8",
    )

    from engine_v3 import review_provenance
    from engine_v3.pipelines.paper import _stamp_review_manuscript_hash

    changed = _stamp_review_manuscript_hash(run_dir)

    assert changed is True
    review = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    assert review["review_method"]["reviewed_manuscript_sha256"] == review_provenance.manuscript_sha256(
        run_dir, ("paper_draft_v0.qmd",)
    )


def test_stamp_preserved_when_manuscript_newer_than_review(tmp_path: Path):
    import os, time

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps(
            {
                "delivery": "pass",
                "review_method": {
                    "decision_owner": "hermes",
                    "reviewed_manuscript_sha256": "0" * 64,
                },
            }
        ),
        encoding="utf-8",
    )
    old = time.time() - 100
    os.utime(run_dir / "quality_review_round1.json", (old, old))
    (run_dir / "paper_draft_v0.qmd").write_text("edited AFTER review", encoding="utf-8")

    from engine_v3.pipelines.paper import _stamp_review_manuscript_hash

    assert _stamp_review_manuscript_hash(run_dir) is False
    review = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    assert review["review_method"]["reviewed_manuscript_sha256"] == "0" * 64


def test_citation_dump_section_blocked(tmp_path: Path):
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "## Bibliographic Scope Note\n\n"
        + " ".join("@ref%d" % i for i in range(30)) + "\n",
        encoding="utf-8",
    )
    from engine_v3.pipelines.paper import _validate_citation_distribution

    result = _validate_citation_distribution(tmp_path)
    assert result["valid"] is False
    assert any("citation-dump section" in f for f in result["findings"])
    assert any("packs 30 citations" in f for f in result["findings"])


def test_normal_citation_density_passes(tmp_path: Path):
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "## Related Work\n\nPrior reviews [@a2020; @b2021] and trials [@c2022] differ.\n\n"
        "## Methods\n\nWe follow @d2023 and @e2024.\n",
        encoding="utf-8",
    )
    from engine_v3.pipelines.paper import _validate_citation_distribution

    assert _validate_citation_distribution(tmp_path)["valid"] is True


def test_mojibake_gate_catches_broken_utf8(tmp_path: Path):
    (tmp_path / "references.bib").write_text(
        "@article{z2014,title={Mindfulness in schoolsâ€”a systematic review}}\n",
        encoding="utf-8",
    )
    from engine_v3.pipelines.paper import _validate_text_encoding

    result = _validate_text_encoding(tmp_path)
    assert result["valid"] is False
    assert any("mojibake" in f and "references.bib" in f for f in result["findings"])


def test_operator_findings_channel(tmp_path: Path):
    from engine_v3.pipelines.paper import _operator_findings

    assert _operator_findings(tmp_path)["valid"] is True
    (tmp_path / "operator_findings.md").write_text(
        "# operator QA\n- Figure 2 box texts collide; widen boxes or shorten labels\n",
        encoding="utf-8",
    )
    result = _operator_findings(tmp_path)
    assert result["valid"] is False
    assert any("Figure 2 box texts collide" in f for f in result["findings"])
