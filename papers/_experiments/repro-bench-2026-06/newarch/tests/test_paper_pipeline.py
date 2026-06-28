"""Phase A (full Hermes+Skill pipeline): structural wiring of the 11-phase paper
lane on the framework. The brain/worker phases are validated LIVE on ac-2012 (they
need codex + hermes); here we pin the phase set + the division of labour shape.
"""
from __future__ import annotations

import pytest

from packs.paper import pipeline

pytestmark = pytest.mark.unit


def test_pipeline_has_seven_phases_in_order():
    names = [p.name for p in pipeline.build_paper_phases()]
    assert names == ["data", "gap", "structure", "claim_evidence",
                     "write", "render_gates", "review_heal"]


def test_phases_checkpoint_real_artifacts():
    by = {p.name: p for p in pipeline.build_paper_phases()}
    assert "real_experiments/real_results.json" in by["data"].checkpoint_artifacts
    assert "paper_draft_v0.qmd" in by["write"].checkpoint_artifacts


def test_section_set_is_the_seven_writers():
    assert len(pipeline.SECTIONS) == 7 and "Methods" in pipeline.SECTIONS
