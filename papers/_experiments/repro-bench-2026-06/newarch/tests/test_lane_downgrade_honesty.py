from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3.artifacts.data import ensure_minimal_real_results_and_figures_v3_2

pytestmark = pytest.mark.unit


def _seed_meta_contract_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "research_contract.json").write_text(
        json.dumps(
            {
                "topic": "School-based mindfulness and adolescent outcomes",
                "research_question": "What is the pooled effect?",
                "data_source": {"type": "meta-analysis"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "references.bib").write_text(
        "@article{a2020,title={A},year={2020}}\n"
        "@article{b2021,title={B},year={2021}}\n"
        "@article{c2021,title={C},year={2021}}\n",
        encoding="utf-8",
    )
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "records": [
                    {"doi": "10.1/a", "validation_count": 2},
                    {"doi": "10.1/b", "validation_count": 2},
                    {"doi": "10.1/c", "validation_count": 2},
                ]
            }
        ),
        encoding="utf-8",
    )


def test_escape_hatch_records_explicit_lane_downgrade(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_meta_contract_run(run_dir)

    result = ensure_minimal_real_results_and_figures_v3_2(run_dir)

    assert result["status"] == "done"
    rr = json.loads((run_dir / "real_experiments" / "real_results.json").read_text(encoding="utf-8"))
    downgrade = rr["lane_downgrade"]
    assert downgrade["from"] == "meta-analysis"
    assert downgrade["to"] == "narrative_evidence_map_review"
    assert downgrade["decided_by"] == "data_phase_evidence_floor"
    assert "poolable" in downgrade["reason"]


def test_no_pooled_effects_means_no_forest_plot_fiction(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_meta_contract_run(run_dir)

    ensure_minimal_real_results_and_figures_v3_2(run_dir)

    forest_svg = (run_dir / "figures" / "fig_forest_plot.svg").read_text(encoding="utf-8")
    assert "no pooled effects available" in forest_svg
    assert "No pooled effect estimates were extractable" in forest_svg
    # The fabricated effect intervals (foreign-domain labels) must be gone.
    assert "Energy savings" not in forest_svg
    assert "Baseline error" not in forest_svg
    assert "Risk translation" not in forest_svg


def test_backfilled_figures_use_only_real_run_numbers(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_meta_contract_run(run_dir)

    ensure_minimal_real_results_and_figures_v3_2(run_dir)

    prisma_svg = (run_dir / "figures" / "fig_prisma_flow.svg").read_text(encoding="utf-8")
    # 3 verified references, all two-source verified: only these real counts
    # may appear, no invented identified/screened multipliers.
    assert "Verified bibliography: 3" in prisma_svg
    assert "Two-source verified: 3" in prisma_svg
    assert "Records identified" not in prisma_svg

    method_svg = (run_dir / "figures" / "fig_method_overview.svg").read_text(encoding="utf-8")
    assert "ESCO" not in method_svg
    assert "Evidence acquisition and verification workflow" in method_svg


def test_claim_boundary_states_downgrade_in_manuscript_guidance(tmp_path: Path):
    from engine_v3.pipelines.paper import _structure_claim_boundary

    boundary = _structure_claim_boundary(
        {
            "synthesis": {"numeric_effect_count": 0},
            "lane_downgrade": {
                "from": "meta-analysis",
                "to": "narrative_evidence_map_review",
                "reason": "no extractable poolable effects",
            },
        }
    )

    assert "downgraded from meta-analysis" in boundary
    assert "must not present a forest plot" in boundary
