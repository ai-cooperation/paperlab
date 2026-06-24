from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine_v3.core import DossierStore
from engine_v3.core.orchestrator import EngineV3Orchestrator
from engine_v3.packs.paper import PaperPack
from engine_v3.pipelines.paper import (
    BOUNDED_GOLDEN_OUTPUTS,
    DATA_OUTPUTS,
    FULL_PIPELINE_OUTPUTS,
    bounded_golden_pipeline,
    full_paper_pipeline,
)
from engine_v3.runtimes.codex_cli import CliRunResult, CodexCliRuntime

pytestmark = pytest.mark.unit


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


def test_full_paper_pipeline_runs_all_phases_and_delivery_gate(tmp_path: Path, golden_dir: Path):
    run_dir = tmp_path / "run"
    clean_draft = _clean_long_draft()

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
                '{"p0_count": 0, "delivery": "pass", "floor_100": 82.0}\n',
                encoding="utf-8",
            )
        if "paper_draft_v0.pdf" in prompt:
            (cwd / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
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
        "B",
        "C",
        "D",
        "F",
        "R",
        "Z",
    ]
    assert dossier.artifacts["paper_draft_v0.pdf"].sha256


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
