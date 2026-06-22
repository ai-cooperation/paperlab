from __future__ import annotations

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


def _collect_gate_inputs(
    _task: BrainTask,
    context: RuntimeContext,
) -> Mapping[str, object]:
    return {"gate_inputs": paperctl._build_dossier(context.run_dir)}
