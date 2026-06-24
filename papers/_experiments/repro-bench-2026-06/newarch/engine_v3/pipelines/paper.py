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

DATA_REPAIR_PROMPT = """Repair the paper data phase until the data gates pass.

You are continuing an existing run directory. Inspect the existing artifacts and the
blocking gate report below, then update the declared data artifacts in place.

Hard requirements:
- references.bib must meet the journal reference floor: at least 35 real bibliography entries.
- doi_audit.json must honestly audit DOI/metadata quality for the updated bibliography.
- real_experiments/real_results.json must be regenerated or updated from the expanded evidence.
- figures must remain consistent with real_results.json.
- If the topic cannot yield poolable effects, keep Gate E honest but still satisfy Gate A.
- Do not stop after explaining the blocker; produce the repaired files.
"""

RENDER_GATE_OUTPUTS = [
    "paper_draft_v0.qmd",
    "paper_springer.qmd",
]

RENDER_REPAIR_PROMPT = """Repair the manuscript render/readability gates.

You are continuing an existing run directory. Inspect the blocking gate report below,
paper_draft_v0.qmd, paper_springer.qmd, section files, claim_evidence_map.md,
real_experiments/real_results.json, and references.bib. Update the declared manuscript
artifacts in place.

Hard requirements:
- Expand the manuscript body to satisfy the readability floor (at least 3000 words).
- For Gate F failures, inspect evidence.fail_items and fix each concrete logic-audit item.
- Preserve factual consistency with real_results.json and claim_evidence_map.md.
- Keep figures and citations referenced by existing artifact paths/keys.
- Remove placeholders, outline fragments, and underdeveloped sections.
- Ensure paper_springer.qmd remains renderable after the expansion.
- Do not stop after explaining the blocker; produce the repaired files.
"""

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
REVIEW_OUTPUTS = ["quality_review_round1.json", "quality_review_log.md"]
FORMAT_REPAIR_OUTPUTS = ["paper_draft_v0.pdf"]

CLAIM_EVIDENCE_REPAIR_PROMPT = """Repair Gate B claim-evidence failures.

You are continuing an existing run directory. Inspect the blocking gate report below,
paper_draft_v0.qmd, sections/*.md, claim_evidence_map.md, real_experiments/real_results.json,
doi_audit.json, and references.bib. Update claim_evidence_map.md and, if the gate evidence
identifies an overclaim in the manuscript, also rewrite the unsupported sentence in the
manuscript so every claim is no stronger than the available evidence.

Hard requirements:
- For every flagged Gate B claim, either add an exact claim-evidence row proving it from
  real_results/references or downgrade/delete the unsupported claim in the manuscript.
- Remove or hedge strong causal, universal, state-of-the-art, or outperformance language
  unless directly supported by real_results and citations.
- Keep numeric claims exact with real_experiments/real_results.json.
- Do not stop after explaining the blocker; produce the repaired files.
"""

REVIEW_HEAL_PROMPT = """Run review and self-heal, not review-only.

Inspect the manuscript, figures, claim_evidence_map.md, references.bib, doi_audit.json,
real_experiments/real_results.json, and render logs. Fix any P0/P1 issues you can fix
inside the run directory, then write quality_review_round1.json.

Hard requirements for quality_review_round1.json:
- Include top-level p0_count, delivery, and floor_100 fields for the R gate.
- Include top-level review_loop with status, rounds, reviewer_model, fixer_model,
  floor_failed, and independent_reviewer fields.
- Set delivery to "pass" only if no P0 issues remain and the manuscript can be delivered.
- If issues remain, include actionable findings and keep delivery as "revise".
- Do not stop at review_only when the issue is fixable; modify the affected artifacts.

Hard requirements for quality_review_log.md:
- Record each evaluator/fixer round in order.
- Record every blocking finding, exact edit/fix applied, and recheck result.
- If the loop cannot clear, write the terminal blocker instead of passing.
"""

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
            repair_prompt=DATA_REPAIR_PROMPT,
            max_repair_attempts=2,
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
            repair_prompt=CLAIM_EVIDENCE_REPAIR_PROMPT,
            max_repair_attempts=2,
        ),
        PhaseSpec(
            id="render_gates",
            handler=_collect_gate_inputs,
            prompt="Render journal source and run manuscript gates.",
            expected_outputs=list(RENDER_GATE_OUTPUTS),
            gate_ids=["C", "D", "F"],
            repair_prompt=RENDER_REPAIR_PROMPT,
            max_repair_attempts=2,
        ),
        PhaseSpec(
            id="review_heal",
            handler=_collect_gate_inputs,
            prompt=REVIEW_HEAL_PROMPT,
            expected_outputs=list(REVIEW_OUTPUTS),
            gate_ids=["R"],
            repair_prompt=REVIEW_HEAL_PROMPT,
            max_repair_attempts=3,
            review_rounds=3,
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
    review_log_path = context.run_dir / "quality_review_log.md"
    gate_inputs["review_log_present"] = review_log_path.is_file() and bool(
        review_log_path.read_text(encoding="utf-8", errors="ignore").strip()
    )
    return {"gate_inputs": gate_inputs}
