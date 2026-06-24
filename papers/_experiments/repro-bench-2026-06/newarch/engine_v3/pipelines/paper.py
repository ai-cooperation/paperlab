from __future__ import annotations

import json
from typing import Mapping

import paperctl

from engine_v3.core import BrainTask, PhaseSpec, RuntimeContext


DATA_OUTPUTS = [
    "research_contract.json",
    "references.bib",
    "doi_audit.json",
    "real_experiments/real_results.json",
    "figures/fig_benchmark_comparison.png",
    "figures/fig_benchmark_comparison.svg",
    "figures/fig_forest_plot.png",
    "figures/fig_forest_plot.svg",
    "figures/fig_method_overview.png",
    "figures/fig_method_overview.svg",
    "figures/fig_prisma_flow.png",
    "figures/fig_prisma_flow.svg",
]

RENDER_GATE_OUTPUTS = [
    "paper_draft_v0.qmd",
    "paper_springer.qmd",
]

BOUNDED_GOLDEN_OUTPUTS = DATA_OUTPUTS + RENDER_GATE_OUTPUTS

GAP_OUTPUTS = ["phase3_positioning.md"]
STRUCTURE_OUTPUTS = ["phase4_structure.md"]
CLAIM_EVIDENCE_OUTPUTS = ["claim_evidence_map.md"]
WRITE_OUTPUTS = [
    "sections/introduction.md",
    "sections/related_work.md",
    "sections/methods.md",
    "sections/results.md",
    "sections/discussion.md",
    "sections/limitations.md",
    "sections/conclusion.md",
    "paper_draft_v0.qmd",
]
REVIEW_OUTPUTS = ["quality_review_round1.json"]
FORMAT_REPAIR_OUTPUTS = ["paper_draft_v0.pdf"]

FULL_PIPELINE_OUTPUTS = (
    DATA_OUTPUTS
    + GAP_OUTPUTS
    + STRUCTURE_OUTPUTS
    + CLAIM_EVIDENCE_OUTPUTS
    + WRITE_OUTPUTS
    + ["paper_springer.qmd"]
    + REVIEW_OUTPUTS
    + FORMAT_REPAIR_OUTPUTS
)


def bounded_golden_pipeline() -> list[PhaseSpec]:
    """A deterministic v3 M3 proof over selected golden gates.

    The frozen v2 golden fixture is known to fail B/F. This bounded proof selects
    the stable deterministic gates A/E and C/D so v3 can prove runtime delegation,
    artifact hashing, gate execution, and checkpoint shape before full paper
    quality is re-earned.
    """
    return [
        PhaseSpec(
            id="data",
            handler=_collect_gate_inputs,
            prompt="Replay bounded golden data artifacts through v3 runtime.",
            expected_outputs=list(DATA_OUTPUTS),
            gate_ids=["A", "E"],
        ),
        PhaseSpec(
            id="render_gates",
            handler=_collect_gate_inputs,
            prompt="Replay bounded golden manuscript artifacts through v3 runtime.",
            expected_outputs=list(RENDER_GATE_OUTPUTS),
            gate_ids=["C", "D"],
        ),
    ]


def full_paper_pipeline() -> list[PhaseSpec]:
    return [
        PhaseSpec(
            id="data",
            handler=_collect_gate_inputs,
            prompt="Run paper data phase: verified refs, real results, and figures.",
            expected_outputs=list(DATA_OUTPUTS),
            gate_ids=["A", "E"],
        ),
        PhaseSpec(
            id="gap",
            handler=_collect_gate_inputs,
            prompt="Write paper gap and positioning analysis.",
            expected_outputs=list(GAP_OUTPUTS),
        ),
        PhaseSpec(
            id="structure",
            handler=_collect_gate_inputs,
            prompt="Write paper structure plan.",
            expected_outputs=list(STRUCTURE_OUTPUTS),
        ),
        PhaseSpec(
            id="write",
            handler=_collect_gate_inputs,
            prompt="Draft isolated sections and compose paper_draft_v0.qmd.",
            expected_outputs=list(WRITE_OUTPUTS),
        ),
        PhaseSpec(
            id="claim_evidence",
            handler=_collect_gate_inputs,
            prompt="Write claim-evidence map for every quantitative manuscript claim.",
            expected_outputs=list(CLAIM_EVIDENCE_OUTPUTS),
            gate_ids=["B"],
        ),
        PhaseSpec(
            id="render_gates",
            handler=_collect_gate_inputs,
            prompt="Render journal source and run manuscript gates.",
            expected_outputs=["paper_springer.qmd"],
            gate_ids=["C", "D", "F"],
        ),
        PhaseSpec(
            id="review_heal",
            handler=_collect_gate_inputs,
            prompt="Run review/heal pass and write structured review result.",
            expected_outputs=list(REVIEW_OUTPUTS),
            gate_ids=["R"],
        ),
        PhaseSpec(
            id="format_repair",
            handler=_collect_gate_inputs,
            prompt="Run final format repair and produce delivery PDF.",
            expected_outputs=list(FORMAT_REPAIR_OUTPUTS),
            gate_ids=["Z"],
        ),
    ]


def _collect_gate_inputs(
    _task: BrainTask,
    context: RuntimeContext,
) -> Mapping[str, object]:
    gate_inputs = paperctl._build_dossier(context.run_dir)
    review_path = context.run_dir / "quality_review_round1.json"
    if review_path.is_file():
        try:
            review = json.loads(review_path.read_text(encoding="utf-8"))
            if isinstance(review, dict):
                gate_inputs["review"] = review
        except json.JSONDecodeError:
            gate_inputs["review"] = {"p0_count": 1, "delivery": "invalid-json"}
    return {"gate_inputs": gate_inputs}
