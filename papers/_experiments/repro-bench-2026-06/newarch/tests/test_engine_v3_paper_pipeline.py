from __future__ import annotations

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


def test_review_heal_applies_exact_reviewer_replacements_and_marks_loop_passed(tmp_path: Path):
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
    assert review["delivery"] == "pass"
    assert review["review_loop"]["status"] == "passed"
    assert review["review_loop"]["floor_failed"] is False
    assert "deterministic_review_heal" in (run_dir / "quality_review_log.md").read_text(encoding="utf-8")
    assert replacement in (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")


def test_review_heal_regenerates_flagged_figures_and_marks_loop_passed(tmp_path: Path):
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
    assert review["delivery"] == "pass"
    assert review["review_loop"]["independent_reviewer"] is True
    assert (fig_dir / "fig_prisma_flow.png").stat().st_size > 1000
    assert "deterministic_review_heal" in (run_dir / "quality_review_log.md").read_text(encoding="utf-8")


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
                "# Quality review log\n\n- round 1: passed; no P0; floor ok\n",
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
    assert "paper_draft_v0.qmd" not in review_heal.expected_outputs
    assert "paper_springer.qmd" not in review_heal.expected_outputs
    assert "sections/results.md" not in review_heal.expected_outputs
    assert review_heal.repair_expected_outputs is not None
    assert "paper_draft_v0.qmd" in review_heal.repair_expected_outputs
    assert "paper_springer.qmd" in review_heal.repair_expected_outputs
    assert "sections/results.md" in review_heal.repair_expected_outputs
    assert "Do not treat manuscript edits alone as completion" in review_heal.prompt
    assert "dimensions" in review_heal.prompt
    assert "academic_rigor" in review_heal.prompt
    assert "concrete_fix" in review_heal.prompt
    assert "legacy v2 audit artifacts" in review_heal.prompt
    assert "must not fail delivery solely because they are absent" in review_heal.prompt


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
        "The SMD pool included k = 8 effects. "
        "The pooled standardised mean difference was -0.4327, which indicates a reduction "
        "in depressive symptoms favouring exercise. "
        "Heterogeneity was considerable, with I-squared of 95.4, and this is consistent "
        "with a diverse study pool spanning different exercise modalities. "
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
