from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from engine_v3.core import DossierStore
from engine_v3.core.orchestrator import EngineV3Orchestrator
from engine_v3.packs.paper import PaperPack
from engine_v3.pipelines.paper import BOUNDED_GOLDEN_OUTPUTS, bounded_golden_pipeline
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
