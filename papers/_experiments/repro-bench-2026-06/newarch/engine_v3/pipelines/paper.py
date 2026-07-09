from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping

import format_repair
import paperctl

from engine_v3 import assembly as engine_assembly
from engine_v3 import review_provenance
from engine_v3.packs import paper_artifacts
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
FIGURE_OUTPUTS = [rel for rel in DATA_OUTPUTS if rel.startswith("figures/")]

REVIEW_DIMENSION_ALIASES = {
    "academic rigor": "academic_rigor",
    "academic_rigor": "academic_rigor",
    "citation accuracy": "citation_accuracy",
    "citation verification": "citation_accuracy",
    "citation_accuracy": "citation_accuracy",
    "experimental completeness": "experimental_completeness",
    "experimental_completeness": "experimental_completeness",
    "format and figure table quality": "format_compliance",
    "format and figure/table quality": "format_compliance",
    "format compliance": "format_compliance",
    "format_compliance": "format_compliance",
    "figure table quality": "format_compliance",
    "figure/table quality": "format_compliance",
    "innovation and contribution positioning": "novelty_positioning",
    "innovation positioning": "novelty_positioning",
    "novelty positioning": "novelty_positioning",
    "novelty/positioning": "novelty_positioning",
    "novelty_positioning": "novelty_positioning",
    "practical feasibility": "practical_feasibility",
    "practical_feasibility": "practical_feasibility",
    "writing quality": "writing_quality",
    "writing_quality": "writing_quality",
}

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

DATA_PHASE_PROMPT = """Run paper data phase: verified refs, real results, and figures.

Acceptance criteria before you stop:
- references.bib must contain at least 35 real bibliography entries.
- doi_audit.json must show doi_real_rate >= 0.80 or an equivalent two-source
  verification rate for the retained bibliography.
- Prefer DOI-backed, two-source-verifiable references. If the core topic has fewer
  directly matching studies, add adjacent method, dataset, background, and policy
  references that are still relevant to the manuscript.
- real_experiments/real_results.json must contain extractable real numeric evidence
  for the paper's empirical claims.
- figures must be generated from real_results.json and remain consistent with it.
- Do not stop after producing a diagnostic; write the declared artifacts.
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
    # ADR-001: the model authors structural values + prose SOURCES; the harness
    # assembles paper_draft_v0.qmd deterministically (it stays declared so the
    # missing-output loop routes back to the model when assembly fails closed).
    "paper_meta.json",
    "sections/00_abstract.md",
    "sections/introduction.md",
    "sections/related_work.md",
    "sections/methods.md",
    "sections/results.md",
    "sections/discussion.md",
    "sections/limitations.md",
    "sections/conclusion.md",
    "paper_draft_v0.qmd",
]

PAPER_META_CONTRACT_PROMPT = """
paper_meta.json contract (STRICT — unknown keys are rejected, no prose inside):
{
  "schema_version": "paper_meta.v1",
  "layout": "paper",
  "title": "<manuscript title>",
  "authors": [{"name": "Cooperation.TW", "email": "paperlab@cooperation.tw"}],
  "abstract_ref": "sections/00_abstract.md",
  "bibliography": "references.bib",
  "section_order": ["sections/introduction.md", "sections/related_work.md",
                    "sections/methods.md", "sections/results.md",
                    "sections/discussion.md", "sections/limitations.md",
                    "sections/conclusion.md"],
  "keywords": ["<3-6 keywords>"]
}
- Write the abstract PROSE (>= 40 words, no heading line, never a placeholder) to
  sections/00_abstract.md. Abstract prose must NEVER be placed in paper_meta.json.
- Do NOT hand-write paper_draft_v0.qmd or paper_springer.qmd: the harness assembles
  them deterministically from paper_meta.json + sections/*.md and OVERWRITES any
  hand-written copy on every phase.
"""

GAP_PHASE_PROMPT = """Write the required research positioning artifact.

You are continuing an existing run directory. Inspect research_contract.json,
references.bib, doi_audit.json, real_experiments/real_results.json, and figures/.

Hard requirements:
- Write phase3_positioning.md. This exact file is the declared output.
- Include literature landscape, gap matrix, differentiation statement, contribution echo,
  and claim boundaries.
- Align the gap with the actual data artifacts. If the data does not support the original
  method claim, downgrade the paper framing honestly instead of leaving the phase blocked.
- Do not stop after explaining uncertainty; produce the declared artifact.
"""

STRUCTURE_PHASE_PROMPT = """Write the required paper structure artifact.

You are continuing an existing run directory. Inspect research_contract.json,
phase3_positioning.md, references.bib, doi_audit.json, real_experiments/real_results.json,
and figures/.

Hard requirements:
- Write phase4_structure.md. This exact file is the declared output.
- Include the manuscript architecture: Abstract, Introduction, Related Work, Methods,
  Results, Discussion, Limitations, and Conclusion.
- Include key claims, evidence sources, planned figures/tables, and claim boundaries.
- Align the structure with the actual research method and data artifacts; if the data
  only supports an evidence map, protocol, or observational association, explicitly
  downgrade the structure and title claims.
- Do not stop after explaining uncertainty; produce the declared artifact with honest
  limitations and next-phase instructions.
"""
REVIEW_OUTPUTS = ["quality_review_round1.json", "quality_review_log.md"]
REVIEW_HEAL_OUTPUTS = (
    REVIEW_OUTPUTS
    + WRITE_OUTPUTS
    # the reviewer must be able to FIX what it (or a gate) flags: claim map
    # thinness, bib mojibake (round 17: the em-dash fix was impossible because
    # references.bib was not in the allowed output set)
    + ["paper_springer.qmd", "claim_evidence_map.md", "references.bib"]
    + FIGURE_OUTPUTS
)
REVIEW_HEAL_REPAIR_OUTPUTS = REVIEW_HEAL_OUTPUTS
FORMAT_REPAIR_OUTPUTS = ["paper_draft_v0.pdf"]

WRITE_REPAIR_PROMPT = """Repair the write phase missing manuscript outputs.

You are continuing an existing run directory. Inspect phase3_positioning.md,
phase4_structure.md, research_contract.json, references.bib, doi_audit.json,
real_experiments/real_results.json, figures/, assembly_block_report.json (if
present — it names exactly what blocked assembly), and any partial sections.

Hard requirements:
- Write every declared section file under sections/ (including
  sections/00_abstract.md) and paper_meta.json.
- Use real citation keys from references.bib and real figure paths from figures/.
- Keep the paper aligned with phase4_structure.md and real_results.json.
- Do not stop after explaining the blocker; produce the missing files.
""" + PAPER_META_CONTRACT_PROMPT

CLAIM_EVIDENCE_REPAIR_PROMPT = """Repair Gate B claim-evidence failures.

You are continuing an existing run directory. Inspect the blocking gate report below,
paper_draft_v0.qmd, sections/*.md, claim_evidence_map.md, real_experiments/real_results.json,
doi_audit.json, and references.bib. Update claim_evidence_map.md and, if the gate evidence
identifies an overclaim in the manuscript, also rewrite the unsupported sentence in the
manuscript so every claim is no stronger than the available evidence.

Hard requirements:
- For every flagged Gate B claim, either add an exact claim-evidence row proving it from
  real_results/references or downgrade/delete the unsupported claim in the manuscript.
- For scope-overreach findings such as "first-line", "state-of-the-art", or
  "outperform", the repaired evidence row must include the exact phrase and the
  citation/source that proves that scope; otherwise remove or hedge that phrase in
  the affected manuscript sentence.
- Remove or hedge strong causal, universal, state-of-the-art, or outperformance language
  unless directly supported by real_results and citations.
- Keep numeric claims exact with real_experiments/real_results.json.
- Do not return unchanged files. If a flagged claim remains word-for-word in
  paper_draft_v0.qmd, the repair is incomplete.
- Do not stop after explaining the blocker; produce the repaired files.
"""

REVIEW_HEAL_PROMPT = """Run review and self-heal with mandatory review artifacts.

Inspect the manuscript, figures, claim_evidence_map.md, references.bib, doi_audit.json,
real_experiments/real_results.json, and render logs. Fix any P0/P1 issues you can fix
inside the run directory, then write quality_review_round1.json.

The first required deliverable is always the review record. Overwrite
quality_review_round1.json and quality_review_log.md during this Hermes run even if no
manuscript edit is needed. Do not treat manuscript edits alone as completion.

Citation markers are load-bearing (binding): [@citekey] tokens in the body are the
source of the rendered inline citations and the References list. NEVER drop or
paraphrase them away when editing or rewriting prose - a rewrite that loses them
delivers a PDF with an empty References section and is blocked by the delivery
gate. If the manuscript already reads well and cites its bibliography, do NOT
rewrite it; review it as it stands.

Ordering (binding): the review record must be the LAST files you write. The verdict
is hash-bound to the manuscript bytes it reviewed, so ANY edit to a manuscript file
(qmd, sections/*.md, figures, references.bib) AFTER the review record is written makes
the verdict stale and blocks the phase. Finish every repair and surface sync first,
then perform the final review pass, then write quality_review_round1.json and
quality_review_log.md. If you must touch a manuscript file afterwards, re-run the
final review pass and re-write both review files again as the last step.

Hard requirements for quality_review_round1.json:
- Include top-level p0_count, delivery, and floor_100 fields for the R gate.
- floor_100 must be a numeric 0-100 score. If detailed floor findings are needed,
  put them in floor_100_details, not in floor_100.
- Include top-level review_loop with status, rounds, reviewer_model, fixer_model,
  floor_failed, and independent_reviewer fields. review_loop.status must be exactly
  "passed" when the loop cleared or "blocked_revise" when it did not; do not invent
  variants.
- independent_reviewer means: the verdict came from a dedicated final review pass
  over the finished manuscript AFTER all repairs in this run, applying the selected
  review skill with fresh eyes (the manuscript hash stamp corroborates this). It
  does not mean a different model reviewed. Set it to true when you performed that
  dedicated pass; set it to false only if you skipped it and graded during repair —
  a false value blocks delivery.
- Include top-level dimensions with exactly these expert-review dimensions:
  academic_rigor, novelty_positioning, experimental_completeness, writing_quality,
  practical_feasibility, citation_accuracy, and format_compliance.
- Each dimensions entry must include a numeric score from 0 to 10 and a concise rationale.
- Use the seven-dimension expert-review rubric: academic rigor 25%, novelty/positioning
  30%, experimental completeness 20%, writing quality 15%, practical feasibility 10%,
  plus citation accuracy and format compliance as mandatory non-weighted checks.
- Include top-level findings as a list. Each finding must include severity, location,
  issue, concrete_fix, and rationale. If no P0/P1 findings remain, include any P2/P3
  issues found; use an empty list only after explicitly checking all seven dimensions.
- Set delivery to "pass" only if no P0 issues remain and the manuscript can be delivered.
- If issues remain, include actionable findings and keep delivery as "revise".
- Do not stop at review_only when the issue is fixable; modify the affected artifacts.

Figure and citation hard requirements (figure-design skill, binding):
- Figures may ONLY be produced with matplotlib in an academic style: no hand-written
  SVG, no title text embedded inside the image (the caption carries the title), axis
  labels >= 14pt, nothing clipped at the image border, restrained colors.
- Every bibliography entry must be cited IN the body section it supports. Do not
  create any scope-note / bibliographic-note section and do not pack citations into
  one paragraph - that is gate-gaming and will be blocked.

Deterministic blocker worklist:
- If pending_content_findings.md exists in the run directory, every line in it is a
  deterministic delivery-gate blocker computed from run artifacts. Fix each one in ALL
  manuscript surfaces (paper_draft_v0.qmd, paper_springer.qmd, and the matching
  sections/*.md) before writing the review. Delivery cannot be "pass" while any
  pending finding remains unfixed.
- operator_findings.md is owned by the human operator: never edit or clear it (any
  edit you make is reverted). Fix the findings in the manuscript; the operator clears
  the file after independently verifying your fix.

Hard requirements for review_method (capability decision trace):
- You own the review decision. Inspect the review capabilities visible in your skill
  context and choose the one that fits a domain-expert review of this manuscript.
  Do not wait for the harness to pick a skill for you.
- Include top-level review_method with: schema_version "paperlab.review_method.v3.2",
  decision_owner "hermes", capability_class "domain_expert_review", selected_skill
  (the capability you actually applied), selection_reason, vip_capability_required,
  vip_capability_available, and inputs_checked (the artifact paths you inspected).
- Do not fabricate the trace: selected_skill must be a capability you can actually
  see and use. If no reviewer capability is available, keep delivery "revise", set
  vip_capability_available to false, and state the gap instead of pretending an
  expert review happened.

Hard requirements for quality_review_log.md:
- Record each evaluator/fixer round in order.
- Include a "## Skill Decision Trace" section listing the review capabilities you
  saw, the skill you selected, why, and the input artifacts you checked.
- Record the seven dimension scores and every remaining finding.
- Record every blocking finding, exact edit/fix applied, and recheck result.
- If the loop cannot clear, write the terminal blocker instead of passing.

V3.2 boundary:
- legacy v2 audit artifacts such as doi_verification_report.md, gate_report.json,
  figure_audit.md, coherence_audit.md, and gate_d_readability.md are not required
  V3.2 review outputs and must not fail delivery solely because they are absent.
- You review the manuscript SOURCE (qmd/sections). The delivery PDF is owned
  entirely by the next phase (format_repair renders it from scratch) and by
  deterministic gates. NO property of the PDF is reviewable here: not its absence
  (it is deleted by design before your run), not its staleness, not its content.
  Any finding about paper_draft_v0.pdf or artifact_manifest.json PDF references
  is out of scope and must not appear in your review.
- If real_results.json records a lane_downgrade, judge the manuscript AS the
  downgraded deliverable (e.g. an honest evidence-map/narrative review), not as an
  incomplete version of the originally contracted synthesis. Grading a downgraded
  run against the original contract type re-blocks a decision the product owner
  already made; instead verify the downgrade is stated and no pooled claims leak.
- If review finds fixable manuscript, table, citation, or visual-layout issues, repair
  paper_draft_v0.qmd, paper_springer.qmd, and the affected sections within this phase.
- Every manuscript fix must be applied to paper_draft_v0.qmd, paper_springer.qmd, AND
  the matching sections/*.md file. A fix applied only to the qmd re-infiltrates from
  the stale section file on the next recomposition.
"""

REVIEW_HEAL_REPAIR_PROMPT = """Run bounded final re-review after deterministic structural repairs.

The harness has already applied mechanical V3.2 repairs before this repair attempt:
- references.bib abstract-field coverage is normalized with explicit unavailable placeholders when needed.
- claim_evidence_map.md includes the V3.2 exact-match audit addendum when prior rows can be mapped.
- paper_draft_v0.qmd and paper_springer.qmd include citation/link frontmatter for blue clickable citations.
- exact reviewer replacement fixes may already have been applied when the previous review gave target/replacement text.

Hard boundary:
- First inspect the current artifacts after deterministic structural repairs.
- Verify whether previously reported P0/P1 items are actually resolved in the current files.
- Overwrite quality_review_round1.json and quality_review_log.md after any repair.
- Citation markers are load-bearing (binding): never drop [@citekey] tokens when
  editing prose; a rewrite that loses them renders an empty References section
  and is blocked by the delivery gate.
- Ordering (binding): the review record must be the LAST files you write. Any edit to
  a manuscript file (qmd, sections/*.md, figures, references.bib) after the review
  record makes the hash-bound verdict stale and blocks the phase; if that happens,
  re-review and re-write both review files again as the final step.
- You may edit manuscript/source/figure artifacts listed in the allowed output set when
  the blocking review finding is fixable; deterministic structural repairs are already
  handled by the harness before this task.
- Keep delivery as "revise" with concrete findings if any P0 remains.
- Set delivery to "pass" only if no P0 issues remain and the current PDF/manuscript is deliverable.
- Include the same required review schema as the main review_heal prompt, including
  review_loop, all seven dimensions with 0-10 scores, the review_method capability
  decision trace (decision_owner "hermes", the skill you actually selected and why,
  inputs_checked), and the "## Skill Decision Trace" section in the log.
- A deterministic repair is not a review. You must re-review the repaired manuscript
  yourself before any pass verdict.
- review_loop.independent_reviewer means: the verdict came from a dedicated final
  review pass over the finished manuscript after all repairs (it does not mean a
  different model reviewed). Set it to true when you performed that dedicated pass;
  false blocks delivery.
- If pending_content_findings.md exists, every line is a deterministic delivery-gate
  blocker; fix each in ALL manuscript surfaces before any pass verdict.
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
            gate_ids=["A", "E", "G"],
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
            prompt=DATA_PHASE_PROMPT,
            expected_outputs=list(DATA_OUTPUTS),
            gate_ids=["A", "E", "G"],
            repair_prompt=DATA_REPAIR_PROMPT,
            max_repair_attempts=2,
        ),
        PhaseSpec(
            id="gap",
            handler=_collect_gate_inputs,
            prompt=GAP_PHASE_PROMPT,
            expected_outputs=list(GAP_OUTPUTS),
            repair_prompt=GAP_PHASE_PROMPT,
            repair_expected_outputs=list(GAP_OUTPUTS),
            max_repair_attempts=2,
        ),
        PhaseSpec(
            id="structure",
            handler=_collect_gate_inputs,
            prompt=STRUCTURE_PHASE_PROMPT,
            expected_outputs=list(STRUCTURE_OUTPUTS),
            repair_prompt=STRUCTURE_PHASE_PROMPT,
            repair_expected_outputs=list(STRUCTURE_OUTPUTS),
            max_repair_attempts=2,
        ),
        PhaseSpec(
            id="write",
            handler=_collect_gate_inputs,
            prompt=(
                "Draft isolated section sources under sections/ (including "
                "sections/00_abstract.md) and write paper_meta.json; the harness "
                "assembles paper_draft_v0.qmd deterministically from them.\n"
                + PAPER_META_CONTRACT_PROMPT
            ),
            expected_outputs=list(WRITE_OUTPUTS),
            repair_prompt=WRITE_REPAIR_PROMPT,
            repair_expected_outputs=list(WRITE_OUTPUTS),
            max_repair_attempts=2,
        ),
        PhaseSpec(
            id="claim_evidence",
            handler=_collect_gate_inputs,
            prompt="Write claim-evidence map for every quantitative manuscript claim.",
            expected_outputs=list(CLAIM_EVIDENCE_OUTPUTS),
            gate_ids=["B"],
            repair_prompt=CLAIM_EVIDENCE_REPAIR_PROMPT,
            repair_expected_outputs=list(CLAIM_EVIDENCE_OUTPUTS + WRITE_OUTPUTS),
            max_repair_attempts=3,
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
            expected_outputs=list(REVIEW_HEAL_OUTPUTS),
            gate_ids=["R"],
            repair_prompt=REVIEW_HEAL_REPAIR_PROMPT,
            repair_expected_outputs=list(REVIEW_HEAL_REPAIR_OUTPUTS),
            max_repair_attempts=3,
            review_rounds=3,
        ),
        PhaseSpec(
            id="format_repair",
            handler=_format_repair_handler,
            gate_ids=["Z"],
            # ADR-001 §V4-C: a done format_repair must not be skipped on resume
            # while the delivered PDF is stale against its render sources.
            staleness_probe=engine_assembly.is_delivery_stale,
        ),
    ]


def _collect_gate_inputs(
    _task: BrainTask,
    context: RuntimeContext,
) -> Mapping[str, object]:
    from engine_v3.artifacts import (
        build_data_substeps_v3_2,
        load_or_build_canonical_data,
        run_data_harness_v3_2,
    )

    data_harness = None
    if _task.phase == "data":
        data_harness = run_data_harness_v3_2(context.run_dir, list(DATA_OUTPUTS))
        substeps = build_data_substeps_v3_2(context.run_dir)
    else:
        load_or_build_canonical_data(context.run_dir, write=True, schema_version="v3.2")
        substeps = []
    # ADR-001 §V4-C: every qmd-reading phase re-derives the generated draft from
    # the current sources FIRST (write-if-changed; legacy runs no-op), so a healer
    # edit to sections/*.md is always visible to the gates — the infinite-heal-loop
    # hole both v3 reviewers converged on.
    assembly_state = None
    if _task.phase in ("write", "claim_evidence", "render_gates", "review_heal"):
        assembly_state = engine_assembly.ensure_assembled(context.run_dir)
    if _task.phase == "gap":
        _ensure_phase3_positioning_v3_2(context.run_dir)
    if _task.phase == "structure":
        _ensure_phase4_structure_v3_2(context.run_dir)
    if _task.phase == "write":
        _ensure_write_outputs_v3_2(context.run_dir)
    if _task.phase == "claim_evidence":
        _soften_fallback_claim_boundary_language(context.run_dir)
        _downgrade_unsupported_qualitative_overclaims(context.run_dir)
        _ensure_minimal_claim_evidence_map_v3_2(context.run_dir)
        _augment_traceable_claim_evidence_rows(context.run_dir)
    if _task.phase == "render_gates":
        # No padding here: readability/table floors are the writer's job. If the
        # body is thin, Gate D must block and route repair back to Hermes
        # (V3_2_SPEC.md Decisions: no deterministic content padding to pass gates).
        _ensure_paper_springer_source_v3_2(context.run_dir)
        _repair_generated_content_quality_v3_2(context.run_dir)
        _normalize_thousands_separators_for_gate_f(context.run_dir)
    pending_content: list[str] = []
    if _task.phase == "review_heal":
        # The delivery PDF is the PREVIOUS format_repair's render and is
        # definitionally stale during review_heal. Round 8: the reviewer read
        # it, found the already-fixed caption, and issued a P0 revise that kept
        # the run from ever reaching the re-render. Remove it so the reviewer
        # audits manuscript sources; format_repair re-renders from scratch.
        (context.run_dir / "paper_draft_v0.pdf").unlink(missing_ok=True)
        # ⚠️ Ordering contract (round 5, v3_0f6a0c83f9cf): once the verdict is
        # pass, the manuscript is FINAL and the harness must not touch it -
        # re-applying the review's target/replacement prescriptions to a
        # pass-reviewed manuscript stripped the just-woven citations and
        # invalidated the hash-bound verdict, the exact review-last violation
        # the prompts pin on Hermes. Prescriptions apply only to revise
        # verdicts (the reviewer asked for those edits; a re-review follows).
        review_now = _read_json(context.run_dir / "quality_review_round1.json") or {}
        delivery_now = str(review_now.get("delivery") or "").strip().lower()
        if delivery_now not in ("pass", "passed", "ok"):
            _apply_review_structural_repairs(context.run_dir)
            _apply_exact_review_replacements(context.run_dir)
            _repair_generated_content_quality_v3_2(context.run_dir)
            _ensure_minimal_claim_evidence_map_v3_2(context.run_dir)
        _ensure_review_record_v3_2(context.run_dir)
        _normalize_review_record_schema(context.run_dir)
        # The bridge runs AFTER any harness mutation so the worklist describes
        # the manuscript state the gate will actually judge (round 5: bridge
        # ran first, saw citations present, then the replacement stripped them
        # and the citation finding vanished from the worklist).
        pending_content = _surface_pending_content_findings(context.run_dir)
        _stamp_review_manuscript_hash(context.run_dir)
    gate_inputs = paperctl._build_dossier(context.run_dir)
    if data_harness is not None:
        gate_inputs["data_completeness"] = data_harness["completeness"]
    if assembly_state is not None:
        gate_inputs["assembly"] = {
            "ok": assembly_state.ok,
            "changed": assembly_state.changed,
            "findings": list(assembly_state.blocked_findings),
        }
    review_path = context.run_dir / "quality_review_round1.json"
    if review_path.is_file():
        try:
            review = json.loads(review_path.read_text(encoding="utf-8"))
            if isinstance(review, dict):
                gate_inputs["review"] = review
        except json.JSONDecodeError:
            gate_inputs["review"] = {"p0_count": 1, "delivery": "invalid-json"}
    review_log_path = context.run_dir / "quality_review_log.md"
    review_log_text = (
        review_log_path.read_text(encoding="utf-8", errors="ignore")
        if review_log_path.is_file()
        else ""
    )
    gate_inputs["review_log_present"] = bool(review_log_text.strip())
    gate_inputs["review_log_text"] = review_log_text[:40000]
    gate_inputs["manuscript_sha256"] = review_provenance.manuscript_sha256(
        context.run_dir, paper_artifacts.review_manuscript_files(context.run_dir)
    )
    if _task.phase == "review_heal":
        gate_inputs["pending_content_findings"] = pending_content
    artifacts = {
        rel: context.run_dir / rel
        for rel in _task.expected_outputs
        if (context.run_dir / rel).is_file()
    }
    return {"gate_inputs": gate_inputs, "substeps": substeps, "artifacts": artifacts}


def _ensure_phase3_positioning_v3_2(run_dir: Path) -> bool:
    path = run_dir / "phase3_positioning.md"
    existing = path.read_text(encoding="utf-8", errors="ignore").strip() if path.is_file() else ""
    if existing:
        return False
    contract = _read_json(run_dir / "research_contract.json") or _read_json(run_dir / "research_contract.input.json")
    real_results = _read_json(run_dir / "real_experiments" / "real_results.json")
    refs_text = (run_dir / "references.bib").read_text(encoding="utf-8", errors="ignore") if (run_dir / "references.bib").is_file() else ""
    refs_count = _count_bib_entries(refs_text)
    method_label = _structure_method_label(real_results)
    claim_boundary = _structure_claim_boundary(real_results)
    title = str(contract.get("topic") or "Untitled Paper").strip()
    research_question = str(contract.get("research_question") or "TBD").strip()
    contribution = str(contract.get("contribution") or "TBD").strip()
    body = f"""# Research Positioning

## Literature Landscape

This positioning artifact was generated deterministically because the Hermes gap task did not produce the declared output. It uses the current V3.2 run artifacts rather than inventing literature conclusions.

- Topic: {title}
- Research question: {research_question}
- Verified bibliography size: {refs_count}
- Data/method artifact: {method_label}

The literature framing should therefore be conservative: compare the proposed paper against adjacent verified references, but do not claim a completed pooled effect, causal identification, or best-in-class method unless real_results.json explicitly supports it.

## Gap Matrix

| Gap | Description | Existing Work | Our Approach |
|-----|-------------|---------------|--------------|
| G1 | Scope specificity | Prior work addresses adjacent constructs, populations, or methods but does not exactly match the run contract. | Keep the manuscript anchored to the specific topic and research question above. |
| G2 | Evidence transparency | Many papers report conclusions without exposing the reference-verification and data-artifact chain. | Use references.bib, doi_audit.json, and real_results.json as the auditable evidence path. |
| G3 | Claim calibration | The available V3.2 artifacts may support an observational, evidence-map, or protocol-style contribution rather than the strongest original framing. | Downgrade claims to the method artifact actually present: {method_label}. |

## Differentiation Statement

Unlike a generic literature summary, this paper is positioned as an auditable V3.2 manuscript whose claims must be traceable to verified references and real_results.json. The differentiator is not rhetorical novelty alone; it is the bounded link between the research contract, verified bibliography, generated figures, and explicit claim limits.

## Contribution Echo

1. Define a focused research question and make the evidence boundary explicit.
2. Use verified bibliography and data artifacts to constrain the manuscript's claims.
3. Carry the method framing into the structure, writing, claim-evidence, and review phases without overstating unsupported results.

{claim_boundary}

## Implications for the Next Phase

The structure phase should preserve this conservative framing, include planned figures/tables, and instruct the write phase to use only citation keys and numeric claims that can be traced to the run artifacts.
"""
    path.write_text(body, encoding="utf-8")
    return True


def _ensure_phase4_structure_v3_2(run_dir: Path) -> bool:
    path = run_dir / "phase4_structure.md"
    existing = path.read_text(encoding="utf-8", errors="ignore").strip() if path.is_file() else ""
    if existing:
        return False
    contract = _read_json(run_dir / "research_contract.json") or _read_json(run_dir / "research_contract.input.json")
    real_results = _read_json(run_dir / "real_experiments" / "real_results.json")
    positioning = (run_dir / "phase3_positioning.md").read_text(encoding="utf-8", errors="ignore")
    refs_count = _count_bib_entries((run_dir / "references.bib").read_text(encoding="utf-8", errors="ignore") if (run_dir / "references.bib").is_file() else "")
    method_label = _structure_method_label(real_results)
    claim_boundary = _structure_claim_boundary(real_results)
    figure_plan = _structure_figure_plan(run_dir)
    title = str(contract.get("topic") or "Untitled Paper").strip()
    research_question = str(contract.get("research_question") or "TBD").strip()
    contribution = str(contract.get("contribution") or "TBD").strip()
    gap_excerpt = _positioning_excerpt(positioning)
    body = f"""# Phase 4 Structure

## Source Alignment

- Source contract: research_contract.json
- Positioning source: phase3_positioning.md
- Data source: real_experiments/real_results.json
- Reference pool: {refs_count} bibliography entries
- Method framing: {method_label}

## Working Title

{title}

## Research Question

{research_question}

## Contribution Boundary

{contribution}

{claim_boundary}

## Manuscript Architecture

### Abstract

State the topic, data source, method framing, core empirical or evidence-map result, and the main limitation in one compact paragraph. Avoid causal or pooled-effect claims unless real_results.json explicitly supports them.

### 1. Introduction

Introduce the applied problem, explain why the chosen exposure/intervention/evidence base matters, and end with a claim that matches the available data artifacts. The final paragraph should list the contribution without exceeding the claim boundary.

### 2. Related Work

Organize prior work around the gaps identified in phase3_positioning.md. Use the following positioning anchor:

> {gap_excerpt}

### 3. Methods

Describe the verified data source, evidence acquisition process, DOI/reference verification, and the analysis type reported in real_results.json. If the run is non-poolable or evidence-map based, state that explicitly and do not imply completed meta-analysis.

### 4. Results

Report only metrics traceable to real_results.json, doi_audit.json, references.bib, and generated figures. Separate evidence coverage, model/analysis outputs, and limitations.

### 5. Discussion

Interpret the findings conservatively. Explain how the result changes the literature framing, what it does not prove, and what future full-text extraction or causal identification would be required.

### 6. Limitations

Include data coverage, measurement, omitted-variable, publication metadata, non-poolability, and external-validity limits as applicable.

### 7. Conclusion

Restate the bounded contribution and its practical implication without introducing new evidence.

## Planned Figures and Tables

{figure_plan}

## Key Claims to Carry Forward

1. The manuscript must only use claims supported by real_results.json or verified reference metadata.
2. Any causal, best-in-class, universal, or pooled-effect language must be downgraded unless exact evidence exists.
3. The write phase must preserve this structure and produce section files plus paper_draft_v0.qmd.

## Next Phase Instructions

- Draft all sections from this outline.
- Use real citation keys from references.bib.
- Keep figure references aligned with the files in figures/.
- Preserve the claim boundaries above during claim-evidence and review gates.
"""
    path.write_text(body, encoding="utf-8")
    return True


def _ensure_write_outputs_v3_2(run_dir: Path) -> bool:
    """Deterministic ASSEMBLY only, never content synthesis.

    ⚠️ The writer is Hermes. This helper used to synthesize whole boilerplate
    sections ("The manuscript should keep claims traceable to ...") when Hermes
    wrote nothing - the source of the 2026-07-02 Potemkin papers. Now it may
    only compose paper_draft_v0.qmd from SUBSTANTIVE Hermes-written section
    files. Missing or thin sections stay missing so the orchestrator's
    missing-output repair loop routes the work back to Hermes.
    """
    # ADR-001 path: when the model authored paper_meta.json, assembly IS the write
    # composer — deterministic, fail-closed, single-Abstract by construction. The
    # legacy composer below stays for old-contract runs until live validation
    # retires it (plan 8a/8b).
    if (run_dir / engine_assembly.PAPER_META_FILE).is_file():
        return engine_assembly.assemble_paper(run_dir).changed
    qmd_path = run_dir / "paper_draft_v0.qmd"
    if qmd_path.is_file():
        return False
    section_names = [
        "introduction",
        "related_work",
        "methods",
        "results",
        "discussion",
        "limitations",
        "conclusion",
    ]
    sections: dict[str, str] = {}
    for name in section_names:
        path = run_dir / "sections" / ("%s.md" % name)
        if not path.is_file():
            return False
        body = path.read_text(encoding="utf-8", errors="ignore").strip()
        # An outline fragment is not a section; composing it would launder thin
        # content past the write phase into Gate D.
        if len(body.split()) < 80:
            return False
        sections[name] = body
    contract = _read_json(run_dir / "research_contract.json") or _read_json(run_dir / "research_contract.input.json")
    title = str(contract.get("topic") or "Untitled Paper").strip()
    refs_text = (run_dir / "references.bib").read_text(encoding="utf-8", errors="ignore") if (run_dir / "references.bib").is_file() else ""
    citation_keys = _first_citation_keys(refs_text, limit=10)
    qmd_path.write_text(_compose_qmd_v3_2(title, citation_keys, sections), encoding="utf-8")
    return True


def _first_citation_keys(bib: str, *, limit: int) -> list[str]:
    keys: list[str] = []
    for match in re.finditer(r"(?ms)^@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=^@\w+\s*\{|\Z)", bib or ""):
        key = match.group(1).strip()
        body = match.group(2)
        if not key:
            continue
        if not re.search(r"\bauthor\s*=", body, flags=re.IGNORECASE):
            continue
        if not re.search(r"\byear\s*=", body, flags=re.IGNORECASE):
            continue
        keys.append(key)
        if len(keys) >= limit:
            break
    return keys


def _citation_cluster(keys: list[str]) -> str:
    if not keys:
        return ""
    return "[" + "; ".join("@%s" % key for key in keys) + "]"


def _real_results_summary(real_results: dict[str, Any]) -> str:
    sample = real_results.get("sample")
    if isinstance(sample, dict):
        parts = []
        for key in ("n_country_year_complete", "n_countries", "year_min", "year_max"):
            if sample.get(key) is not None:
                parts.append("%s=%s" % (key, sample.get(key)))
        if parts:
            return "The analysis artifact reports " + ", ".join(parts) + "."
    if real_results.get("reference_count") is not None:
        return "The evidence-map artifact reports reference_count=%s and two_source_verified=%s." % (
            real_results.get("reference_count"),
            real_results.get("two_source_verified"),
        )
    gate_a = real_results.get("gate_a_reference_floor")
    if isinstance(gate_a, dict):
        return "The bibliography artifact reports bibliography_entries=%s and passed=%s." % (
            gate_a.get("bibliography_entries"),
            gate_a.get("passed"),
        )
    return "The available real_results.json artifact defines the current evidence boundary for the manuscript."


def _section_text(title: str, paragraphs: list[str], claim_boundary: str) -> str:
    boundary = re.sub(r"^##\s*", "", claim_boundary.strip(), flags=re.MULTILINE)
    expanded = []
    for paragraph in paragraphs:
        expanded.append(paragraph)
    expanded.extend(_section_quality_paragraphs(title))
    expanded.append(boundary)
    return "## %s\n\n%s\n" % (title, "\n\n".join(expanded))


def _section_quality_paragraphs(title: str) -> list[str]:
    normalized = title.lower()
    if normalized == "introduction":
        return [
            "The introduction therefore frames the work as a bounded research artifact: it states the motivating gap, names the available evidence, and avoids claims that would require data not present in the run directory.",
            "A reader should be able to distinguish the topic ambition from the evidence actually assembled in this run before reaching the methods section.",
            "The opening argument should identify why the research question matters, what prior work or practice leaves unresolved, and which part of that gap can be addressed with the present artifacts.",
            "When the contract contains a strong claim, the introduction restates it as a testable objective rather than as an achieved conclusion. This keeps novelty language separate from evidence language.",
            "The section should also prepare the reader for a conservative interpretation of results, because the paper is only as strong as the verified references, data artifact, and figures available for inspection.",
        ]
    if normalized == "related work":
        return [
            "This section uses the verified bibliography to situate the question, while keeping clear that bibliographic coverage is not the same as full-text evidence synthesis.",
            "The literature discussion should support the research gap and terminology, not substitute for empirical findings that are absent from the result artifact.",
            "The review should group sources by their role in the argument: background evidence, methodological precedent, measurement context, and unresolved limitation.",
            "A reference can justify terminology or motivate the research design, but it should not be used to imply that this run has completed analyses that are missing from real_results.json.",
            "The strongest related-work contribution is therefore comparative positioning: it explains what the current draft can add and where it remains narrower than a full systematic review or full empirical study.",
        ]
    if normalized == "methods":
        return [
            "The methods description is limited to reproducible steps represented by local artifacts: contract parsing, bibliography verification, result-artifact construction, figure generation, and claim-evidence checking.",
            "Any method component that is not represented by a run artifact is described as future work rather than as completed analysis.",
            "The manuscript should state the unit of analysis, data source, inclusion boundary, verification rule, and transformation path whenever those fields are available.",
            "If the run produced only an evidence map, the method is a structured evidence-mapping workflow. If it produced model outputs, the method can describe the model family and diagnostics only to the extent present in the artifact.",
            "This prevents the methods section from becoming a generic promise of analysis and gives reviewers a concrete checklist for reproducing or challenging the pipeline.",
        ]
    if normalized == "results":
        return [
            "The results narrative separates evidence coverage from measured effects. It reports values only when those values are present in real_results.json or in the verified artifact summary.",
            "Figures and tables are treated as summaries of available artifacts, so the text does not infer pooled effects, model diagnostics, or causal mechanisms unless those outputs exist.",
            "When the result artifact contains sample coverage, the section reports coverage before interpretation. When it contains model coefficients, the section describes sign, uncertainty, and boundary conditions without overstating causality.",
            "When the result artifact is non-poolable, the section explains why quantitative pooling is deferred and what evidence was still verified.",
            "This ordering keeps the results section useful even for constrained runs: readers first see what was measured, then what can be interpreted, and finally what remains outside scope.",
        ]
    if normalized == "discussion":
        return [
            "The discussion interprets the artifact as a quality-controlled draft rather than a final disciplinary claim. It emphasizes what can be audited and what still requires stronger extraction, modeling, or external validation.",
            "This framing keeps the manuscript useful for review while preventing the formatting pipeline from hiding evidentiary limits.",
            "The discussion should connect the paper back to the research question, but it should not convert a bounded artifact into a field-wide conclusion.",
            "If the available evidence is mainly bibliographic, the discussion can explain implications for research design, data needs, and future evidence collection.",
            "If the available evidence includes empirical estimates, the discussion can compare interpretation paths while preserving uncertainty and avoiding unsupported policy or clinical recommendations.",
        ]
    if normalized == "limitations":
        return [
            "The limitations are part of the claim contract. They identify missing full-text checks, unverified causal assumptions, limited model diagnostics, or non-poolable evidence when those constraints apply.",
            "Stating these limits in the manuscript is required before the output can be treated as a deliverable research draft.",
            "The section should distinguish limitations of the source data, limitations of the automated pipeline, and limitations of the current manuscript state.",
            "A limitation is not a formatting apology; it is a boundary on what readers may infer from the draft.",
            "The section should therefore name the exact missing evidence that would be needed to upgrade the conclusion, such as study-level coding, duplicate screening, external validation, richer covariates, or sensitivity analysis.",
        ]
    if normalized == "conclusion":
        return [
            "The conclusion restates only the contribution supported by the run artifacts and avoids introducing new results.",
            "The strongest acceptable takeaway is that the pipeline produced a traceable draft under explicit evidence limits; stronger domain conclusions require richer data artifacts.",
            "The conclusion should preserve the distinction between a manuscript that is technically deliverable and a manuscript that is ready for disciplinary submission.",
            "If the artifact is sufficient for a bounded draft, the conclusion can identify the narrow contribution and the next validation step.",
            "If the artifact is weak, the conclusion should remain provisional and direct future work toward the missing evidence rather than claiming completion.",
        ]
    return [
        "This section states only claims that can be checked against the local run artifacts.",
    ]


def _compose_qmd_v3_2(title: str, citation_keys: list[str], sections: dict[str, str]) -> str:
    bibliography = "references.bib"
    cite = _citation_cluster(citation_keys[:3])
    abstract_cite = (" " + cite) if cite else ""
    body = "\n\n".join(sections[name] for name in [
        "introduction",
        "related_work",
        "methods",
        "results",
        "discussion",
        "limitations",
        "conclusion",
    ])
    return f"""---
title: "{title.replace('"', "'")}"
author:
  - name: Cooperation.TW
    email: paperlab@cooperation.tw
bibliography: {bibliography}
format:
  pdf:
    pdf-engine: xelatex
number-sections: true
link-citations: true
---

## Abstract

This V3.2 manuscript draft is generated from verified run artifacts. It summarizes the research contract, the verified bibliography, the real-results artifact, and the explicit claim boundaries that govern later review.{abstract_cite}

{body}

## References
"""


def _ensure_paper_springer_source_v3_2(run_dir: Path) -> bool:
    target = run_dir / "paper_springer.qmd"
    draft = run_dir / "paper_draft_v0.qmd"
    if target.is_file() and target.read_text(encoding="utf-8", errors="ignore").strip():
        # ⚠️ P0 gate breakout (2026-07-07): an existing springer is NOT trusted
        # blindly. Retro-rerun jobs carried a pre-V3.2 springer with a stale
        # 'Abstract pending.' stub in the RENDER surface while the draft was
        # cleaned; the early return here never resynced it, so three jobs
        # reached the VIP station (one done_pass on the public site) with a
        # double-Abstract PDF. Resync the abstract from a clean draft.
        return _resync_springer_abstract_from_draft(run_dir)
    if not draft.is_file():
        return False
    text = draft.read_text(encoding="utf-8", errors="ignore")
    if "link-citations:" not in text:
        text = _insert_qmd_yaml_flag(text, "link-citations: true")
    if "number-sections:" not in text:
        text = _insert_qmd_yaml_flag(text, "number-sections: true")
    target.write_text(text, encoding="utf-8")
    return True


def _resync_springer_abstract_from_draft(run_dir: Path) -> bool:
    """When paper_springer.qmd's frontmatter abstract is a stub but the draft's
    is real/clean, copy the draft abstract into springer (preserving springer's
    own render flags). Returns True if it changed springer."""
    springer_path = run_dir / "paper_springer.qmd"
    draft_path = run_dir / "paper_draft_v0.qmd"
    if not springer_path.is_file() or not draft_path.is_file():
        return False
    springer = springer_path.read_text(encoding="utf-8", errors="ignore")
    draft = draft_path.read_text(encoding="utf-8", errors="ignore")
    s_front = re.match(r"(?s)\A---(.*?)---", springer)
    d_front = re.match(r"(?s)\A---(.*?)---", draft)
    if not s_front or not d_front:
        return False
    s_abstract = _frontmatter_abstract(s_front.group(1)) or ""
    d_abstract = _frontmatter_abstract(d_front.group(1))
    s_is_stub = bool(_ABSTRACT_STUB_RE.search(s_abstract) and len(s_abstract) < 120)
    if not s_is_stub:
        return False
    # The draft was cleaned in one of two ways: (a) the abstract key was
    # replaced with a real abstract, or (b) the abstract key was removed
    # entirely (draft has NO frontmatter abstract). The render-surface springer
    # must match either way: copy a real draft abstract in, or drop the stub
    # abstract when the draft has none. Never leave a stub in the render
    # surface. (2026-07-07: ESG/Transfer/DTP3 draft abstracts were removed,
    # not rewritten, so a copy-only resync silently did nothing.)
    if d_abstract and not _ABSTRACT_STUB_RE.search(d_abstract):
        new_front = _replace_frontmatter_abstract(s_front.group(1), d_abstract)
    else:
        new_front = _remove_frontmatter_abstract(s_front.group(1))
    if new_front == s_front.group(1):
        return False
    updated = "---" + new_front + "---" + springer[s_front.end():]
    springer_path.write_text(updated, encoding="utf-8")
    return True


def _remove_frontmatter_abstract(front: str) -> str:
    """Drop the abstract block (inline or block scalar) from a frontmatter
    string entirely."""
    lines = front.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if re.match(r"^abstract:\s*", lines[i]):
            i += 1
            while i < len(lines) and (not lines[i].strip() or re.match(r"^\s{2,}\S", lines[i])):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "".join(out)


def _replace_frontmatter_abstract(front: str, new_abstract: str) -> str:
    """Replace the abstract block (inline or block scalar) in a frontmatter
    string with a block-scalar abstract carrying new_abstract."""
    lines = front.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if re.match(r"^abstract:\s*", line) and not replaced:
            out.append("abstract: |\n")
            out.append("  " + new_abstract.strip() + "\n")
            replaced = True
            i += 1
            # skip the old abstract's continuation (block-scalar indented lines)
            while i < len(lines) and (not lines[i].strip() or re.match(r"^\s{2,}\S", lines[i])):
                i += 1
            continue
        out.append(line)
        i += 1
    return "".join(out)


def _insert_qmd_yaml_flag(text: str, flag: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[:end] + "\n" + flag + text[end:]
    return "---\n%s\n---\n\n%s" % (flag, text)


def _ensure_minimum_readability_body_v3_2(run_dir: Path, *, floor: int = 3000) -> bool:
    changed = False
    for rel in ("paper_draft_v0.qmd", "paper_springer.qmd"):
        path = run_dir / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = _strip_generated_boilerplate_v3_2(text)
        text = _dedupe_generated_section_v3_2(text, "V3.2 Traceability and Claim Discipline Addendum")
        if len(text.split()) >= floor:
            if text != path.read_text(encoding="utf-8", errors="ignore"):
                path.write_text(text.rstrip() + "\n", encoding="utf-8")
                changed = True
            continue
        if "## Evidence Boundary Notes" in text:
            continue
        appendix = _readability_addendum_text()
        repaired = text.rstrip()
        repaired += "\n\n" + appendix
        path.write_text(repaired + "\n", encoding="utf-8")
        changed = True
    return changed


def _readability_addendum_text() -> str:
    return """## Evidence Boundary Notes

This note is included only when the manuscript body is too thin for review. It does not introduce empirical results. Its purpose is to make the evidence boundary explicit so that the next review pass can decide whether the draft should proceed, be repaired, or remain blocked.

The manuscript should treat research_contract.json as the source of the research intent, references.bib and doi_audit.json as the source of bibliography and DOI verification, real_experiments/real_results.json as the source of empirical or evidence-map results, and generated figures as visual summaries of those artifacts. Claims that cannot be tied to those files should remain tentative or be removed during the claim-evidence and review phases.

The data artifact determines the strength of the contribution. If it reports an observational panel model, the manuscript may discuss associations, model specifications, sample coverage, and robustness limits. If it reports an evidence map or bibliography-centered result, the manuscript may discuss coverage, coding readiness, and research positioning, but should not claim pooled effect sizes, dose-response estimates, moderator significance, or causal effects.

This discipline is important for production use because a generated manuscript can otherwise sound more complete than its artifacts. The paper should therefore separate what was searched, what was verified, what was measured, what was modeled, and what remains outside scope. That separation makes later review meaningful and prevents the PDF from passing format checks while failing substantive review.

The next review step should inspect each section for overclaiming, missing citation support, untraceable numbers, and inconsistent figure references. If the reviewer finds a mismatch, the repair loop should revise the text toward the artifact boundary rather than inventing new evidence. The acceptable outcome is a cautious but deliverable draft, not a confident draft unsupported by data.
"""


def _ensure_quarto_tables_v3_2(run_dir: Path) -> bool:
    changed = False
    for rel in ("paper_draft_v0.qmd", "paper_springer.qmd"):
        path = run_dir / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _quarto_real_table_count(text) >= 2:
            continue
        text = text.rstrip() + "\n\n" + _traceability_tables_text(run_dir)
        path.write_text(text.rstrip() + "\n", encoding="utf-8")
        changed = True
    return changed


def _repair_generated_content_quality_v3_2(run_dir: Path) -> bool:
    changed = False
    readable_citation_keys = set(_first_citation_keys(
        (run_dir / "references.bib").read_text(encoding="utf-8", errors="ignore")
        if (run_dir / "references.bib").is_file()
        else "",
        limit=10_000,
    ))
    for rel in ("paper_draft_v0.qmd", "paper_springer.qmd"):
        path = run_dir / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        repaired = _strip_generated_boilerplate_v3_2(text)
        repaired = _remove_unreadable_citation_clusters_v3_2(repaired, readable_citation_keys)
        repaired = _dedupe_generated_section_v3_2(
            repaired,
            "V3.2 Traceability and Claim Discipline Addendum",
        )
        repaired = _dedupe_generated_section_v3_2(repaired, "Traceability Tables")
        repaired = re.sub(r"\n{3,}", "\n\n", repaired).strip() + "\n"
        if repaired != text:
            path.write_text(repaired, encoding="utf-8")
            changed = True
    return changed


def _remove_unreadable_citation_clusters_v3_2(text: str, readable_keys: set[str]) -> str:
    if not readable_keys:
        return re.sub(r"\s*\[(?:@[A-Za-z0-9_:\-.]+(?:\s*;\s*)?)+\]", "", text)

    def replace(match: re.Match[str]) -> str:
        keys = re.findall(r"@([A-Za-z0-9_:\-.]+)", match.group(0))
        kept = [key for key in keys if key in readable_keys]
        if not kept:
            return ""
        return "[" + "; ".join("@%s" % key for key in kept) + "]"

    return re.sub(r"\[(?:@[A-Za-z0-9_:\-.]+(?:\s*;\s*)?)+\]", replace, text)


def _strip_generated_boilerplate_v3_2(text: str) -> str:
    boilerplate_patterns = [
        r"For V3\.2 production quality, this section keeps the argument explicit, avoids unsupported causal language, and leaves a clear path for claim-evidence auditing\.",
        r"The section is intentionally written as an auditable bridge between the research contract and the available artifacts\. It identifies what the run can support, what remains outside the evidence boundary, and how later review should verify each statement against references\.bib, doi_audit\.json, real_results\.json, generated figures, and the claim-evidence map\.",
    ]
    repaired = text
    for pattern in boilerplate_patterns:
        repaired = re.sub(pattern + r"\s*", "", repaired)
    return repaired


def _dedupe_generated_section_v3_2(text: str, heading: str) -> str:
    pattern = re.compile(
        r"(?ms)^##\s+%s\s*\n.*?(?=^##\s+|\Z)" % re.escape(heading)
    )
    matches = list(pattern.finditer(text))
    if len(matches) <= 1:
        return text
    keep = matches[-1].group(0).strip()
    without = pattern.sub("", text)
    return without.rstrip() + "\n\n## " + heading + "\n\n" + re.sub(r"(?ms)^##\s+%s\s*\n" % re.escape(heading), "", keep).strip() + "\n"


def _quarto_real_table_count(text: str) -> int:
    return len(re.findall(r"(?m)^:\s+.*?\{#tbl-([^}\s]+)([^}]*)\}", text or ""))


def _traceability_tables_text(run_dir: Path) -> str:
    real_results = _read_json(run_dir / "real_experiments" / "real_results.json")
    method = _structure_method_label(real_results)
    return f"""## Traceability Tables

| Artifact | Role | Status |
|---|---|---|
| research_contract.json | Research intent and scope | present |
| references.bib | Verified bibliography entries | present |
| doi_audit.json | DOI and metadata verification | present |
| real_experiments/real_results.json | Data or evidence-map result | {method} |
| claim_evidence_map.md | Claim-to-evidence audit path | present |

: Artifact Traceability {{#tbl-artifact-traceability tbl-colwidths="[32,43,25]"}}

| Claim Area | Allowed Interpretation | Review Boundary |
|---|---|---|
| Evidence coverage | Bibliography and artifact coverage can be described | Do not infer pooled effects without extracted effects |
| Empirical result | Report only real_results.json fields | Do not invent missing model diagnostics |
| Citations | Use keys from references.bib | Do not cite unavailable sources |
| Delivery | PDF may be delivered after gates pass | Format pass does not override evidence limits |

: Claim Boundary Matrix {{#tbl-claim-boundary tbl-colwidths="[26,39,35]"}}
"""


def _count_bib_entries(text: str) -> int:
    return len(re.findall(r"^@\w+\s*\{", text or "", re.MULTILINE))


def _structure_method_label(real_results: dict[str, Any]) -> str:
    for key in ("analysis_id", "analysis_type", "result_type", "schema_version"):
        value = real_results.get(key)
        if value:
            return str(value)
    if isinstance(real_results.get("main_twfe_coefficients"), list):
        return "observational panel analysis"
    return "evidence-map or protocol-style synthesis"


def _structure_claim_boundary(real_results: dict[str, Any]) -> str:
    if isinstance(real_results.get("main_twfe_coefficients"), list):
        return (
            "## Claim Boundaries\n\n"
            "The manuscript may discuss observed associations and model estimates from the panel analysis, "
            "but must avoid definitive causal language unless the model artifact explicitly supports it."
        )
    synthesis = real_results.get("synthesis")
    if isinstance(synthesis, dict) and int(synthesis.get("numeric_effect_count") or 0) == 0:
        downgrade = real_results.get("lane_downgrade")
        downgrade_note = ""
        if isinstance(downgrade, dict) and downgrade:
            downgrade_note = (
                " This run was explicitly downgraded from %s to %s because %s; the manuscript must state "
                "this downgrade in Methods and must not present a forest plot or pooled-effect table."
                % (
                    downgrade.get("from") or "a quantitative synthesis",
                    downgrade.get("to") or "a narrative evidence-map review",
                    downgrade.get("reason") or "no poolable effects were extractable",
                )
            )
        return (
            "## Claim Boundaries\n\n"
            "The manuscript may claim verified evidence coverage and structured research positioning, "
            "but must not claim pooled effect sizes, moderator significance, or dose-response estimates."
            + downgrade_note
        )
    return (
        "## Claim Boundaries\n\n"
        "The manuscript should keep claims traceable to real_results.json, doi_audit.json, references.bib, and generated figures."
    )


def _structure_figure_plan(run_dir: Path) -> str:
    names = [
        "fig_prisma_flow",
        "fig_method_overview",
        "fig_benchmark_comparison",
        "fig_forest_plot",
    ]
    rows = []
    for name in names:
        svg = (run_dir / "figures" / f"{name}.svg").is_file()
        png = (run_dir / "figures" / f"{name}.png").is_file()
        rows.append(f"- {name}: svg={str(svg).lower()}, png={str(png).lower()}")
    rows.append("- Table 1: study/reference characteristics or data-source summary")
    rows.append("- Table 2: model/evidence results traceable to real_results.json")
    return "\n".join(rows)


def _positioning_excerpt(text: str) -> str:
    stripped = re.sub(r"\s+", " ", text or "").strip()
    if not stripped:
        return "phase3_positioning.md is unavailable; preserve contract-level gap framing."
    return stripped[:700]


def _downgrade_unsupported_qualitative_overclaims(run_dir: Path) -> bool:
    from packs.paper import gates

    dossier = paperctl._build_dossier(run_dir)
    draft = str(dossier.get("draft_text") or "")
    if not draft:
        return False
    changed = False
    for claim in gates.extract_claims(draft):
        if not (claim.get("causal") or claim.get("quantifier") or claim.get("overreach")):
            continue
        original = str(claim.get("text") or "").strip()
        repaired = _hedge_overclaim_sentence(original)
        if repaired == original:
            continue
        changed = _replace_in_manuscript_files(run_dir, original, repaired) or changed
    if changed:
        _append_repair_log(
            run_dir,
            "deterministic_claim_evidence_heal",
            "Downgraded unsupported qualitative overclaim language before Gate B.",
        )
    return changed


def _soften_fallback_claim_boundary_language(run_dir: Path) -> bool:
    replacements = [
        (r"\bevery claim is constrained\b", "manuscript claims are constrained"),
        (r"\bevery claim\b", "manuscript claims"),
        (r"\bmust keep claims traceable\b", "should keep claims traceable"),
        (r"\bmust only use claims\b", "should use claims"),
        (r"\bmust not claim\b", "should not claim"),
    ]
    changed = False
    for path in _manuscript_paths(run_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        repaired = text
        for pattern, replacement in replacements:
            repaired = re.sub(pattern, replacement, repaired, flags=re.IGNORECASE)
        if repaired != text:
            path.write_text(repaired, encoding="utf-8")
            changed = True
    return changed


def _hedge_overclaim_sentence(sentence: str) -> str:
    replacements = [
        (r"\bdemonstrates that\b", "suggests that"),
        (r"\bensures that\b", "is consistent with the possibility that"),
        (r"\bguarantees?\b", "is associated with"),
        (r"\bproves?\b", "is consistent with"),
        (r"\bproven\b", "consistent"),
        (r"\bcauses?\b", "is associated with"),
        (r"\bcaused\b", "was associated with"),
        (r"\balways\b", "often"),
        (r"\bevery\b", "many"),
        (r"\bnever\b", "rarely"),
        (r"\bin all cases\b", "in the observed cases"),
        (r"\buniversally\b", "in several settings"),
        (r"\bwithout exception\b", "with exceptions possible"),
        (r"\bstate[- ]of[- ]the[- ]art\b", "competitive"),
        (r"\boutperform(?:s|ing)?\b", "performs competitively with"),
        (r"\bfirst-line\b", "candidate"),
        (r"\bbest-in-class\b", "competitive"),
        (r"\bunprecedented\b", "notable"),
    ]
    repaired = sentence
    for pattern, replacement in replacements:
        repaired = re.sub(pattern, replacement, repaired, flags=re.IGNORECASE)
    return repaired


def _replace_in_manuscript_files(run_dir: Path, target: str, replacement: str) -> bool:
    changed = False
    for path in _manuscript_paths(run_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if target not in text:
            continue
        path.write_text(text.replace(target, replacement), encoding="utf-8")
        changed = True
    return changed


def _normalize_thousands_separators_for_gate_f(run_dir: Path) -> bool:
    changed = False
    pattern = re.compile(r"(?<![\w.])(\d{1,3}),(\d{3})(?![\w.])")
    for path in _manuscript_paths(run_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        normalized = pattern.sub(r"\1\2", text)
        if normalized == text:
            continue
        path.write_text(normalized, encoding="utf-8")
        changed = True
    return changed


def _manuscript_paths(run_dir: Path) -> list[Path]:
    paths = [
        run_dir / "paper_draft_v0.qmd",
        run_dir / "paper_springer.qmd",
    ]
    sections = run_dir / "sections"
    if sections.is_dir():
        paths.extend(sorted(sections.glob("*.md")))
    return [path for path in paths if path.is_file()]


def _apply_exact_review_replacements(run_dir: Path) -> bool:
    review_path = run_dir / "quality_review_round1.json"
    review = _read_json(review_path)
    if not review:
        return False
    findings = review.get("findings")
    if not isinstance(findings, list):
        return False

    actionable = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        target = str(finding.get("target_content") or "").strip()
        replacement = str(finding.get("replacement_content") or "").strip()
        severity = str(finding.get("severity") or "").upper()
        if severity in {"P0", "P1", "CRITICAL", "MAJOR"} or (target and replacement):
            actionable.append((finding, target, replacement))
    if not actionable:
        return False

    applied: list[dict[str, str]] = []
    unresolved: list[str] = []
    for finding, target, replacement in actionable:
        if not target and not replacement and _regenerate_review_flagged_figures(run_dir, finding):
            applied.append({"target": str(finding.get("location") or ""), "replacement": "regenerated figures", "status": "regenerated"})
            finding["status"] = "resolved"
            continue
        if not target and not replacement and _remove_review_flagged_citation(run_dir, finding):
            applied.append({"target": str(finding.get("location") or ""), "replacement": "removed flagged citation", "status": "removed_citation"})
            finding["status"] = "resolved"
            continue
        if not target or not replacement:
            unresolved.append(str(finding.get("issue") or finding.get("id") or "missing exact replacement"))
            continue
        if not _replace_in_manuscript_files(run_dir, target, replacement):
            if _target_absent_from_manuscript(run_dir, target):
                applied.append({"target": target, "replacement": replacement, "status": "already_absent"})
                finding["status"] = "resolved"
                continue
            unresolved.append(target[:160])
            continue
        if _target_absent_from_manuscript(run_dir, target):
            applied.append({"target": target, "replacement": replacement, "status": "replaced"})
            finding["status"] = "resolved"
        else:
            unresolved.append(target[:160])

    if unresolved or not applied:
        return False

    # Deterministic code may apply the reviewer's exact fixes, but it must never
    # certify the verdict. Delivery stays "revise" so the bounded repair round
    # re-runs the Hermes reviewer against the repaired manuscript (V3_2_SPEC.md
    # Decisions: no deterministic pass-like review).
    review["delivery"] = "revise"
    review["findings"] = [finding for finding in findings if not (isinstance(finding, dict) and finding.get("status") == "resolved")]
    loop = review.get("review_loop") if isinstance(review.get("review_loop"), dict) else {}
    loop["status"] = "repairs_applied_rereview_required"
    loop["rounds"] = max(1, int(loop.get("rounds") or 1))
    loop["fixer_model"] = str(loop.get("fixer_model") or "deterministic-review-heal")
    review["review_loop"] = loop
    review["deterministic_review_heal"] = {
        "status": "applied",
        "applied_count": len(applied),
        "method": "exact_reviewer_replacement",
        "rereview_required": True,
    }
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    _append_repair_log(
        run_dir,
        "deterministic_review_heal",
        "Applied %d exact reviewer replacement(s); delivery kept at revise pending Hermes re-review." % len(applied),
    )
    return True


def _regenerate_review_flagged_figures(run_dir: Path, finding: dict[str, Any]) -> bool:
    text = " ".join(str(finding.get(key) or "") for key in ("location", "issue", "concrete_fix", "rationale"))
    stems = sorted(set(re.findall(r"figures/(fig_[A-Za-z0-9_]+)\.(?:png|svg)", text)))
    if not stems or "regenerate" not in text.lower():
        return False
    from engine_v3.artifacts.data import _write_minimal_figure_pair

    real_results = _read_json(run_dir / "real_experiments" / "real_results.json")
    count = _review_figure_reference_count(real_results)
    for stem in stems:
        _write_minimal_figure_pair(run_dir / "figures", stem, count=count, overwrite=True)
    return True


def _remove_review_flagged_citation(run_dir: Path, finding: dict[str, Any]) -> bool:
    text = " ".join(str(finding.get(key) or "") for key in ("location", "issue", "concrete_fix", "rationale"))
    if "out-of-domain" not in text.lower() and "remove" not in text.lower():
        return False
    keys = sorted(set(re.findall(r"@([A-Za-z0-9_:-]+)", text)))
    if not keys:
        keys = sorted(set(re.findall(r"\bentry\s+([A-Za-z0-9_:-]+)\b", text, flags=re.IGNORECASE)))
    if not keys:
        return False
    changed = False
    for key in keys:
        changed = _remove_citation_key_from_manuscripts(run_dir, key) or changed
        changed = _remove_bib_entry(run_dir / "references.bib", key) or changed
    return changed


def _remove_citation_key_from_manuscripts(run_dir: Path, key: str) -> bool:
    changed = False
    citation = "@" + key
    sentence_pattern = re.compile(r"(?s)(?:^|(?<=[.!?])\s+)([^.!?\n]*%s[^.!?\n]*(?:[.!?]|\n|$))" % re.escape(citation))
    for path in _manuscript_paths(run_dir):
        text = path.read_text(encoding="utf-8", errors="ignore")
        repaired = sentence_pattern.sub(" ", text)
        repaired = re.sub(r"[ \t]{2,}", " ", repaired)
        repaired = re.sub(r"\n{3,}", "\n\n", repaired)
        if repaired == text:
            continue
        path.write_text(repaired.strip() + "\n", encoding="utf-8")
        changed = True
    return changed


def _remove_bib_entry(path: Path, key: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(r"@\w+\s*\{\s*%s\s*," % re.escape(key), flags=re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return False
    depth = 0
    end = None
    for index in range(match.start(), len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break
    if end is None:
        return False
    repaired = text[: match.start()].rstrip() + "\n\n" + text[end:].lstrip()
    path.write_text(repaired.rstrip() + "\n", encoding="utf-8")
    return True


def _review_figure_reference_count(real_results: dict[str, Any]) -> int:
    for key in ("reference_count", "two_source_verified", "max_poolable_k"):
        value = real_results.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(1, int(value))
    summary = real_results.get("summary")
    if isinstance(summary, dict):
        value = summary.get("included_references") or summary.get("references")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return max(1, int(value))
    return 1


def _target_absent_from_manuscript(run_dir: Path, target: str) -> bool:
    return all(target not in path.read_text(encoding="utf-8", errors="ignore") for path in _manuscript_paths(run_dir))


def _append_repair_log(run_dir: Path, title: str, body: str) -> None:
    log_path = run_dir / "quality_review_log.md"
    existing = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.is_file() else ""
    log_path.write_text((existing.rstrip() + "\n\n## %s\n\n%s\n" % (title, body)).lstrip(), encoding="utf-8")


def _apply_review_structural_repairs(run_dir: Path) -> bool:
    try:
        from review_structural_repair import repair_run
    except ImportError:
        return False
    result = repair_run(run_dir)
    return bool(result.get("changed")) if isinstance(result, dict) else False


# Single registry consumed by the review worklist, Gate Z, AND the
# revalidation reset (round 15: the revalidator kept its own hard-coded
# three-validator list, so the new citation-dump gate never triggered a
# reset and a dirty manuscript sailed through as all-done).
MOJIBAKE_MARKERS = ("\u00e2\u20ac", "\u00c3\u00a9", "\u00c3\u00a8", "\u00ef\u00bf\u00bd")


def _validate_text_encoding(run_dir: Path) -> dict[str, object]:
    """UTF-8 mojibake in manuscript or bibliography (round 16 residue:
    'schoolsâ€"a' from a double-encoded em-dash in a bib title)."""
    findings: list[str] = []
    for rel in ("paper_draft_v0.qmd", "paper_springer.qmd", "references.bib"):
        path = run_dir / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for marker in MOJIBAKE_MARKERS:
            idx = text.find(marker)
            if idx >= 0:
                findings.append(
                    "mojibake (broken UTF-8) in %s near %r: fix the source string"
                    % (rel, text[max(0, idx - 20):idx + 20].replace("\n", " "))
                )
                break
    return {"valid": not findings, "findings": findings}


def _operator_findings(run_dir: Path) -> dict[str, object]:
    """Human-QA findings channel: each non-empty line of operator_findings.md
    becomes a deterministic worklist item (the reviewer must fix it; the file
    is cleared manually by the operator after verification)."""
    path = run_dir / "operator_findings.md"
    if not path.is_file():
        return {"valid": True, "findings": []}
    lines = [
        line.strip().lstrip("- ")
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return {"valid": not lines, "findings": ["operator finding: %s" % l for l in lines]}


def _validate_assembly_block(run_dir: Path) -> dict[str, object]:
    """ADR-001: a failed deterministic assembly leaves a machine-readable block
    report (sources missing/thin/stub). Delivery must not proceed while the
    sources cannot assemble — the findings route the model to the exact file."""
    report = _read_json(run_dir / engine_assembly.BLOCK_REPORT_FILE)
    if not report:
        return {"valid": True, "findings": []}
    raw = report.get("findings") or ["assembly blocked without findings"]
    return {"valid": False, "findings": ["assembly blocked: %s" % f for f in raw][:6]}


def content_validators():
    return (
        _validate_render_log_overflow,
        _validate_caption_claims,
        _validate_title_language,
        _validate_citation_distribution,
        _validate_citations_rendered,
        _validate_inline_heading_leakage,
        _validate_frontmatter_stub,
        _validate_bib_author_integrity,
        _validate_text_encoding,
        _validate_assembly_block,
        _operator_findings,
    )


def _surface_pending_content_findings(run_dir: Path) -> list[str]:
    """Bridge from deterministic gates to the semantic worker.

    Round 6 (2026-07-03): the review passed while the gate-flagged caption
    survived, because content-finding resets only re-ran the phase without
    telling Hermes WHAT the gate would block. This writes the current
    deterministic content findings (ground truth, recomputed now) where the
    review prompt puts them on Hermes's worklist; gates still re-verify."""
    path = run_dir / "pending_content_findings.md"
    findings: list[str] = []
    for validator in content_validators():
        result = validator(run_dir)
        findings.extend(str(f) for f in (result.get("findings") or []))
    if not findings:
        path.unlink(missing_ok=True)
        return []
    path.write_text(
        "# Pending deterministic content findings\n\n"
        "Each item below WILL be blocked by a deterministic delivery gate.\n"
        "Fix every one in ALL manuscript surfaces (paper_draft_v0.qmd,\n"
        "paper_springer.qmd, and the matching sections/*.md).\n\n"
        + "\n".join("- %s" % f for f in findings)
        + "\n",
        encoding="utf-8",
    )
    return findings


def _stamp_review_manuscript_hash(run_dir: Path) -> bool:
    """Bind the review verdict to the manuscript bytes it was written against.

    This is harness state-keeping, not judgment: right after the Hermes review
    ran in this phase, the manuscript on disk is exactly what it reviewed, so
    stamping the current hash is a faithful record. Gate R and Gate Z later
    fail closed when the manuscript changes after this stamp (the 2026-07-02
    audit found pass verdicts delivered against manuscripts rewritten an hour
    after the review).
    """
    review_path = run_dir / "quality_review_round1.json"
    review = _read_json(review_path)
    if not isinstance(review, dict):
        return False
    method = review.get("review_method")
    if not isinstance(method, dict) or not method:
        return False
    existing_stamp = str(method.get("reviewed_manuscript_sha256") or "").strip()
    stamp_files = paper_artifacts.review_manuscript_files(run_dir)
    current = review_provenance.manuscript_sha256(run_dir, stamp_files)
    if existing_stamp:
        if existing_stamp == current:
            return False
        # Round 13: Hermes repaired the manuscript and rewrote the review in
        # the SAME attempt but copied the previous stamp along. If the review
        # file is newer than every manuscript source, it reviewed the current
        # state - re-stamp faithfully. A review OLDER than the sources keeps
        # its stale stamp so Gate R still catches post-review edits.
        try:
            review_mtime = review_path.stat().st_mtime
            source_mtimes = [
                (run_dir / rel).stat().st_mtime
                for rel in stamp_files
                if (run_dir / rel).is_file()
            ]
        except OSError:
            return False
        if not source_mtimes or review_mtime < max(source_mtimes):
            return False
    method["reviewed_manuscript_sha256"] = current
    review["review_method"] = method
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return True


def _normalize_review_record_schema(run_dir: Path) -> bool:
    review_path = run_dir / "quality_review_round1.json"
    review = _read_json(review_path)
    if not isinstance(review, dict):
        return False

    # Schema normalization only: convert alternate field names and score scales
    # to the canonical V3.2 shape. It must never upgrade the verdict — no status
    # flips, no independent_reviewer coercion, no reviewer/fixer backfill, no
    # floor_failed rewrites (V3_2_SPEC.md Decisions: validators own truth).
    changed = False
    if "p0_count" not in review and isinstance(review.get("p0_findings"), list):
        review["p0_count"] = len(review["p0_findings"])
        changed = True
    if review.get("floor_100") is None:
        overall_score = _numeric_review_value(review.get("overall_score_0_to_10"))
        if overall_score is not None:
            review["floor_100"] = round(overall_score * 10.0, 3) if overall_score <= 10 else overall_score
            changed = True

    loop = review.get("review_loop") if isinstance(review.get("review_loop"), dict) else {}
    if not isinstance(review.get("review_loop"), dict):
        changed = True
    independent = loop.get("independent_reviewer")
    if isinstance(independent, dict):
        loop["independent_reviewer"] = _dict_says_pass_like(independent)
        changed = True
    elif isinstance(independent, str):
        normalized_independent = independent.strip().lower() in {"true", "yes", "pass", "passed", "ok", "done"}
        if loop.get("independent_reviewer") != normalized_independent:
            loop["independent_reviewer"] = normalized_independent
            changed = True

    if not loop.get("status"):
        loop["status"] = "unreported"
        changed = True
    if not isinstance(loop.get("rounds"), int) or isinstance(loop.get("rounds"), bool) or int(loop.get("rounds") or 0) < 1:
        loop["rounds"] = 1
        changed = True
    if review.get("review_loop") != loop:
        review["review_loop"] = loop
        changed = True

    dimensions = review.get("dimensions") if isinstance(review.get("dimensions"), dict) else {}
    if not dimensions:
        converted_dimensions = _convert_alternate_review_dimensions(review.get("dimension_scores_0_to_10"))
        if converted_dimensions:
            dimensions = converted_dimensions
            review["dimensions"] = converted_dimensions
            changed = True
    for value in dimensions.values():
        if not isinstance(value, dict):
            continue
        # Relocate a reasonable non-canonical per-dimension score key into the
        # canonical "score" (E2E job v3_e9e1b75927a6: Hermes wrote
        # {"score_0_10": 8.1} and the gate read no numeric score -> floor 76
        # on an otherwise-clean review). Never clobber an existing score.
        if _numeric_review_value(value.get("score")) is None:
            for alias in ("score_0_10", "score_0_to_10", "score_out_of_10"):
                aliased = _numeric_review_value(value.get(alias))
                if aliased is not None:
                    value["score"] = aliased
                    changed = True
                    break
        score = _numeric_review_value(value.get("score"))
        if score is None or score <= 10:
            continue
        if score <= 100:
            value["score"] = round(score / 10.0, 3)
            changed = True

    # Relocation, not fabrication: reviewers repeatedly express the skill
    # decision as a capability_decision_trace list instead of the flat
    # selected_skill / selection_reason / capability_class fields (round 6:
    # a floor-81.4 p0=0 review failed Gate R three times on exactly these
    # fields while its own trace carried the content). Move the reviewer's
    # words into the canonical slots; when the trace has no selected
    # decision there is nothing to relocate and the gate stays closed.
    method = review.get("review_method")
    if isinstance(method, dict):
        trace = method.get("capability_decision_trace")
        selected = None
        if isinstance(trace, list):
            for entry in trace:
                if isinstance(entry, dict) and str(entry.get("decision") or "").lower() == "selected":
                    selected = entry
                    break
        if selected is not None:
            skill = str(selected.get("skill") or "").strip()
            reason = str(selected.get("reason") or "").strip()
            if skill and not str(method.get("selected_skill") or "").strip():
                method["selected_skill"] = skill
                changed = True
            if reason and not str(method.get("selection_reason") or "").strip():
                method["selection_reason"] = reason
                changed = True
            if skill and not str(method.get("capability_class") or "").strip():
                method["capability_class"] = "domain_expert_review"
                changed = True

    if not changed:
        return False
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    _append_repair_log(
        run_dir,
        "deterministic_review_schema_normalization",
        "Normalized review_loop schema and converted any 0-100 dimension scores to the required 0-10 scale without changing delivery.",
    )
    return True


def _ensure_review_record_v3_2(run_dir: Path) -> bool:
    """Guarantee a review record exists for Gate R to read.

    ⚠️ This backfill may only produce a DIAGNOSTIC record with delivery="revise".
    It must never emit a pass-like verdict: the 2026-07-02 audit found four
    production jobs delivered with a synthesized "deterministic bounded final
    review" pass (floor 82.0 fabricated from word count + file existence).
    A pass verdict can only come from the Hermes reviewer with review_method
    provenance (V3_2_SPEC.md Decisions).
    """
    review_path = run_dir / "quality_review_round1.json"
    log_path = run_dir / "quality_review_log.md"
    draft = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8", errors="ignore") if (run_dir / "paper_draft_v0.qmd").is_file() else ""
    claim_map_present = (run_dir / "claim_evidence_map.md").is_file()
    refs_present = (run_dir / "references.bib").is_file()
    real_results_present = (run_dir / "real_experiments" / "real_results.json").is_file()
    words = len(draft.split())
    artifacts_complete = bool(words >= 3000 and claim_map_present and refs_present and real_results_present)
    stale_incomplete = False
    if review_path.is_file():
        existing_review = _read_json(review_path)
        stale_incomplete = artifacts_complete and _review_record_is_stale_incomplete_artifact_verdict(existing_review)
        if _review_record_has_delivery_schema(existing_review) and not stale_incomplete:
            if not log_path.is_file() or log_path.stat().st_size < 200:
                existing = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.is_file() else ""
                log_path.write_text(
                    (existing.rstrip() + "\n\n## deterministic_review_log_completion\n\nExisting review JSON was preserved; log was expanded so Gate R can audit the review provenance without changing the reviewer verdict.\n").lstrip(),
                    encoding="utf-8",
                )
            return False
        if log_path.is_file():
            existing = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.is_file() else ""
            reason = (
                "Prior review carried a stale incomplete-artifact P0 after V3.2 repairs completed the artifacts; a Hermes re-review is required before delivery."
                if stale_incomplete
                else "Existing review JSON lacked delivery, floor, or dimensions; a diagnostic revise record was written so the repair round can request a complete Hermes review."
            )
            log_path.write_text(
                (existing.rstrip() + "\n\n## deterministic_review_diagnostic\n\n%s\n" % reason).lstrip(),
                encoding="utf-8",
            )
    delivery = "revise"
    floor = 0.0
    p0_count = 1
    dimensions: dict[str, dict[str, Any]] = {}
    if stale_incomplete:
        finding = {
            "severity": "P0",
            "location": "review_heal",
            "issue": "Prior review verdict is stale: it predates the V3.2 repairs that completed the manuscript artifacts.",
            "concrete_fix": "Run the Hermes domain-expert review against the current artifacts and record the capability decision trace.",
            "rationale": "A verdict about an older manuscript state cannot certify the current one.",
        }
    elif not artifacts_complete:
        finding = {
            "severity": "P0",
            "location": "review_heal",
            "issue": "Required manuscript artifacts are still incomplete.",
            "concrete_fix": "Complete draft, claim evidence, references, and real_results, then run the Hermes review.",
            "rationale": "A diagnostic placeholder cannot review incomplete artifacts.",
        }
    else:
        finding = {
            "severity": "P0",
            "location": "review_heal",
            "issue": "No Hermes expert review artifact was produced for this round.",
            "concrete_fix": "Run the Hermes domain-expert review and write quality_review_round1.json with review_method provenance.",
            "rationale": "Deterministic code cannot certify review quality (V3_2_SPEC.md Decisions).",
        }
    review = {
        "schema_version": "paperlab.review.v3.2",
        "reviewer": "deterministic diagnostic placeholder (not an expert review)",
        "p0_count": p0_count,
        "delivery": delivery,
        "floor_100": floor,
        "findings": [finding],
        "dimensions": dimensions,
        "review_loop": {
            "status": "blocked_revise",
            "rounds": 1,
            "reviewer_model": "deterministic diagnostic placeholder",
            "fixer_model": "",
            "floor_failed": True,
            "independent_reviewer": False,
        },
    }
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    log_path.write_text(
        "\n".join(
            [
                "# Quality Review Log",
                "",
                "## deterministic_review_diagnostic",
                "",
                "Reviewer: deterministic diagnostic placeholder (not an expert review).",
                "This record exists only so Gate R has evidence to block on; it certifies nothing.",
                "Decision: %s, floor_100=%s, p0_count=%s." % (delivery, floor, p0_count),
                "Blocking finding: %s" % json.dumps(finding, ensure_ascii=False),
                "Next step: the bounded repair round must run the Hermes domain-expert review with a skill decision trace.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return True


def _review_record_is_stale_incomplete_artifact_verdict(review: Any) -> bool:
    if not isinstance(review, dict):
        return False
    if str(review.get("delivery") or "").lower() in {"pass", "passed", "ok"}:
        return False
    findings_text = json.dumps(review.get("findings") or [], ensure_ascii=False).lower()
    return (
        "required manuscript artifacts are still incomplete" in findings_text
        or "review fallback cannot pass incomplete declared artifacts" in findings_text
    )


def _review_record_has_delivery_schema(review: dict[str, Any]) -> bool:
    if not isinstance(review, dict):
        return False
    dimensions = review.get("dimensions")
    alternate_dimensions = review.get("dimension_scores_0_to_10")
    return (
        str(review.get("delivery") or "").lower() in {"pass", "passed", "revise", "blocked", "fail"}
        and (
            _numeric_review_value(review.get("floor_100")) is not None
            or _numeric_review_value(review.get("overall_score_0_to_10")) is not None
        )
        and ((isinstance(dimensions, dict) and bool(dimensions)) or isinstance(alternate_dimensions, list))
    )


def _convert_alternate_review_dimensions(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    converted: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        dimension = _canonical_review_dimension_name(item.get("dimension") or item.get("name") or item.get("key"))
        score = _numeric_review_value(item.get("score"))
        if not dimension or score is None:
            continue
        converted[dimension] = {
            "score": round(score / 10.0, 3) if score > 10 and score <= 100 else score,
            "rationale": str(item.get("rationale") or item.get("comment") or ""),
        }
    return converted


def _canonical_review_dimension_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"\s+", " ", value.replace("&", "and").strip().lower())
    normalized = re.sub(r"[^a-z0-9_ /-]+", "", normalized)
    normalized = normalized.replace("-", " ")
    return REVIEW_DIMENSION_ALIASES.get(normalized)


def _dict_says_pass_like(value: dict[str, Any]) -> bool:
    if value.get("passed") is True or value.get("used") is True:
        return True
    return str(value.get("delivery_recommendation") or value.get("status") or "").lower() in {
        "pass",
        "passed",
        "ok",
        "done",
    }


def _numeric_review_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _int_review_value(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return default


def _augment_traceable_claim_evidence_rows(run_dir: Path) -> bool:
    """Append exact claim rows for numeric claims fully traceable to real_results.

    Gate B intentionally extracts claims from prose rather than trusting the agent's
    matrix. In practice Hermes can repeatedly rephrase a flagged numeric sentence
    without adding the exact matrix row Gate B requires. This deterministic augment
    is narrow: it only adds rows when every extracted number in the sentence is
    already traceable to real_results, so it cannot launder unsupported numbers.
    """
    from packs.paper import gates

    dossier = paperctl._build_dossier(run_dir)
    draft = str(dossier.get("draft_text") or "")
    real_results = dossier.get("real_results") or {}
    if not draft or not isinstance(real_results, dict):
        return False

    matrix_rows = dossier.get("claim_evidence") or []
    matrix_text = gates._matrix_text(matrix_rows)
    matrix_numbers = {
        n
        for n in (gates._to_number(match.group(1)) for match in gates._NUMBER_RE.finditer(matrix_text))
        if n is not None
    }
    result_numbers = gates._extract_numbers_from_results(real_results)
    additions: list[dict[str, object]] = []
    for claim in gates.extract_claims(draft):
        numbers = list(claim.get("numbers") or [])
        if not numbers:
            continue
        if gates._claim_listed(claim, matrix_text, matrix_numbers):
            continue
        if not all(
            gates._number_in_results(float(number), result_numbers)
            or _is_confidence_level_number(float(number), str(claim["text"]))
            for number in numbers
        ):
            continue
        additions.append({"claim": claim["text"], "numbers": numbers})

    if not additions:
        return False

    path = run_dir / "claim_evidence_map.md"
    existing = path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
    lines: list[str] = []
    if not existing.strip():
        lines.extend(["| Claim | Evidence |", "|---|---|"])
    elif "| Claim | Evidence |" not in existing and "|---|---|" not in existing:
        lines.extend([existing.rstrip(), "", "| Claim | Evidence |", "|---|---|"])
    else:
        lines.append(existing.rstrip())

    for item in additions:
        claim_text = _escape_md_cell(str(item["claim"]))
        numbers = ", ".join(_format_claim_number(float(number)) for number in item["numbers"])
        evidence = (
            "Deterministic V3.2 trace: all extracted claim numbers are present in "
            f"real_experiments/real_results.json ({numbers})."
        )
        lines.append(f"| {claim_text} | {_escape_md_cell(evidence)} |")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return True


def _ensure_minimal_claim_evidence_map_v3_2(run_dir: Path) -> bool:
    path = run_dir / "claim_evidence_map.md"
    if path.is_file() and path.read_text(encoding="utf-8", errors="ignore").strip():
        return False
    rows = [
        (
            "The manuscript scope is bounded by the submitted research contract.",
            "research_contract.json; phase3_positioning.md; phase4_structure.md",
        ),
        (
            "Citation support is limited to the verified bibliography available in the run.",
            "references.bib; doi_audit.json",
        ),
        (
            "Result interpretation is limited to the available run result artifact.",
            "real_experiments/real_results.json",
        ),
        (
            "Delivery figures and tables are summaries of local run artifacts.",
            "figures/; paper_springer.qmd",
        ),
    ]
    lines = [
        "| Claim | Evidence |",
        "|---|---|",
        *[
            "| %s | %s |" % (_escape_md_cell(claim), _escape_md_cell(evidence))
            for claim, evidence in rows
        ],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def _escape_md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _format_claim_number(value: float) -> str:
    return f"{value:.12g}"


def _is_confidence_level_number(value: float, claim_text: str) -> bool:
    if value not in {90.0, 95.0, 99.0}:
        return False
    pattern = r"\b%s\s*%%\s*(?:CI|confidence interval)\b" % int(value)
    return re.search(pattern, claim_text, flags=re.IGNORECASE) is not None


def _format_repair_handler(
    _task: BrainTask,
    context: RuntimeContext,
) -> Mapping[str, object]:
    contract = _read_json(context.run_dir / "research_contract.json")
    if not contract:
        contract = _read_json(context.run_dir / "research_contract.input.json")

    # Never validate a stale ReportLab/fallback PDF from a previous attempt. The v3
    # delivery artifact must be produced by the deterministic Quarto renderer here.
    pdf = context.run_dir / "paper_draft_v0.pdf"
    pdf.unlink(missing_ok=True)

    # ADR-001: re-derive the generated draft from current sources before any render
    # work (write-if-changed; legacy runs no-op). The stamp below binds to SOURCES on
    # new-architecture runs, so this re-derivation can never invalidate a verdict.
    engine_assembly.ensure_assembled(context.run_dir)

    # Review-freshness protocol: this phase's own transforms (springer source,
    # boilerplate strip, number formatting, render fixes) are deterministic and
    # unit-tested, so they may advance the reviewed-manuscript stamp — but only
    # when nothing else touched the manuscript between the review and this phase.
    # Any other post-review mutation leaves a stale stamp and Gate Z fails closed.
    pre_format_sha = review_provenance.manuscript_sha256(
        context.run_dir, paper_artifacts.review_manuscript_files(context.run_dir)
    )

    # No content padding here (no readability addendum, no filler tables): if the
    # manuscript cannot pass D/Z on its own content, the job must fail those gates,
    # not be padded past them (V3_2_SPEC.md Decisions).
    _ensure_paper_springer_source_v3_2(context.run_dir)
    _repair_generated_content_quality_v3_2(context.run_dir)
    repair_result = format_repair.verify_and_repair(context.run_dir, contract)
    post_format_sha = review_provenance.manuscript_sha256(
        context.run_dir, paper_artifacts.review_manuscript_files(context.run_dir)
    )
    review_fresh = _reconcile_review_freshness_after_format_repair(
        context.run_dir, pre_format_sha=pre_format_sha, post_format_sha=post_format_sha
    )

    # ADR-001 §V4-B: record the render-source state the delivered PDF came from —
    # AFTER verify_and_repair, so render-time source normalization (sanitize_bib) is
    # already in the hashed bytes. Gate Z blocks on any later source drift.
    if pdf.is_file():
        engine_assembly.write_render_manifest(context.run_dir)
    delivery_freshness = engine_assembly.freshness_findings(context.run_dir)

    validation = _validate_delivery_pdf(pdf, context.run_dir)
    artifacts = {"paper_draft_v0.pdf": pdf} if pdf.is_file() else {}
    return {
        "gate_inputs": {
            "delivery_pdf_validation": validation,
            "review_freshness": review_fresh,
            "delivery_freshness": delivery_freshness,
            "manuscript_sha256": post_format_sha,
        },
        "artifacts": artifacts,
        "format_repair": repair_result,
    }


def _reconcile_review_freshness_after_format_repair(
    run_dir: Path,
    *,
    pre_format_sha: str,
    post_format_sha: str,
) -> dict[str, object]:
    review_path = run_dir / "quality_review_round1.json"
    review = _read_json(review_path)
    if not isinstance(review, dict):
        return {"fresh": False, "findings": ["quality_review_round1.json missing"]}
    method = review.get("review_method")
    method = method if isinstance(method, dict) else {}
    stamp = str(method.get("reviewed_manuscript_sha256") or "").strip()
    if not stamp:
        return {
            "fresh": False,
            "findings": ["review_method.reviewed_manuscript_sha256 missing; verdict is unbound"],
        }
    if stamp != pre_format_sha:
        return {
            "fresh": False,
            "findings": [
                "review verdict is stale: manuscript changed between the Hermes review and format_repair"
            ],
        }
    if post_format_sha != pre_format_sha:
        method["reviewed_manuscript_sha256"] = post_format_sha
        method.setdefault("post_review_transforms", []).append("format_repair")
        review["review_method"] = method
        review_path.write_text(
            json.dumps(review, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        _append_repair_log(
            run_dir,
            "review_freshness_reconciliation",
            "format_repair applied deterministic transforms; reviewed-manuscript stamp advanced with provenance note.",
        )
    return {"fresh": True, "findings": []}


def _read_json(path):
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _validate_delivery_pdf(pdf, run_dir=None) -> dict[str, object]:
    findings = []
    evidence: dict[str, object] = {
        "path": str(pdf),
        "present": pdf.is_file(),
        "size": pdf.stat().st_size if pdf.is_file() else 0,
        "producer": "",
        "creator": "",
        "raw_citation_count": None,
        "unresolved_marker_count": None,
        "numbered_section_detected": False,
        "table_widths": {},
        "content_quality": {},
    }
    if not pdf.is_file():
        findings.append("paper_draft_v0.pdf is missing")
        return {**evidence, "valid": False, "findings": findings}
    if evidence["size"] < 1000:
        findings.append("paper_draft_v0.pdf is too small to be a rendered manuscript")
    try:
        if not pdf.read_bytes().startswith(b"%PDF"):
            findings.append("paper_draft_v0.pdf does not start with a PDF header")
    except OSError as exc:
        findings.append("paper_draft_v0.pdf is unreadable: %s" % exc)

    info = _run_text(["pdfinfo", str(pdf)], timeout_s=30)
    if info:
        for line in info.splitlines():
            if line.startswith("Producer:"):
                evidence["producer"] = line.split(":", 1)[1].strip()
            if line.startswith("Creator:"):
                evidence["creator"] = line.split(":", 1)[1].strip()
    producer = str(evidence.get("producer") or "")
    creator = str(evidence.get("creator") or "")
    if "ReportLab" in producer:
        findings.append("PDF was produced by ReportLab fallback, not Quarto/Pandoc")
    if producer and not ("xdvipdfmx" in producer or "TeX" in producer or "LaTeX" in creator or "pandoc" in creator):
        findings.append("PDF producer/creator does not look like the Quarto/Pandoc render stack")

    text = _run_text(["pdftotext", "-layout", str(pdf), "-"], timeout_s=60)
    if text:
        raw_cites = len(re.findall(r"\[@[A-Za-z0-9_:\-.]+", text))
        unresolved = text.count("?@") + text.count("(?)") + len(re.findall(r"\?\?", text))
        evidence["raw_citation_count"] = raw_cites
        evidence["unresolved_marker_count"] = unresolved
        evidence["numbered_section_detected"] = bool(re.search(r"(?m)^\s*\d+(?:\.\d+)*\.\s+\S", text))
        if raw_cites:
            findings.append("PDF contains raw Pandoc citation tokens")
        if unresolved:
            findings.append("PDF contains unresolved citation/cross-reference markers")
        if not evidence["numbered_section_detected"]:
            findings.append("PDF has no detected numbered section headings")
        content_quality = _validate_pdf_content_quality(text)
        evidence["content_quality"] = content_quality
        findings.extend(content_quality.get("findings") or [])
    else:
        findings.append("pdftotext could not extract PDF text for validation")

    check_dir = Path(run_dir) if run_dir is not None else pdf.parent
    table_widths = _validate_table_widths(check_dir)
    evidence["table_widths"] = table_widths
    findings.extend(table_widths.get("findings") or [])

    # 2026-07-02 human-QA gaps, now mechanical: renderer-reported overflow
    # (Table 1 column collision), caption claims beyond evidence (Figure 4
    # "pooled estimate" on a poolable_k=0 run), title/body language mismatch.
    render_overflow = _validate_render_log_overflow(check_dir)
    evidence["render_overflow"] = render_overflow
    findings.extend(render_overflow.get("findings") or [])

    caption_claims = _validate_caption_claims(check_dir)
    evidence["caption_claims"] = caption_claims
    findings.extend(caption_claims.get("findings") or [])

    title_language = _validate_title_language(check_dir)
    evidence["title_language"] = title_language
    findings.extend(title_language.get("findings") or [])

    citation_distribution = _validate_citation_distribution(check_dir)
    evidence["citation_distribution"] = citation_distribution
    findings.extend(citation_distribution.get("findings") or [])

    # Round 7 (v3_0f6a0c83f9cf): the delivered PDF had an EMPTY References
    # section while references.bib held 35 verified entries - the woven
    # citations were stripped somewhere between the pass review and the
    # render, and every source-level check missed the final surface. The
    # rendered PDF is the user-facing ground truth; judge it directly.
    rendered_no_stub = _validate_pdf_rendered_no_stub(text or "")
    evidence["rendered_no_stub"] = rendered_no_stub
    findings.extend(rendered_no_stub.get("findings") or [])

    references_rendered = _validate_pdf_references_rendered(text or "", check_dir)
    evidence["references_rendered"] = references_rendered
    findings.extend(references_rendered.get("findings") or [])

    return {**evidence, "valid": not findings, "findings": findings}


def _validate_pdf_rendered_no_stub(pdf_text: str) -> dict[str, object]:
    """The rendered PDF is the user's actual surface. Judge it directly for the
    stub-abstract breakout (2026-07-07): a stale render kept 'Abstract pending.'
    on page 1 even after the source was cleaned, because format_repair resumed
    via preflight gate-recheck and never re-rendered. Cause-agnostic: whatever
    left a stub in the delivered PDF, block it."""
    text = pdf_text or ""
    head = text[:4000]  # page 1 region
    findings: list[str] = []
    if re.search(r"(?i)abstract\s+pending|pending\.\s*$", head, flags=re.MULTILINE) or "Abstract pending" in head:
        findings.append(
            "rendered PDF page 1 contains a placeholder 'Abstract pending.' stub; "
            "the delivered render is stale or the render surface still carries a "
            "stub abstract - re-render from the cleaned source"
        )
    # A double 'Abstract' heading on page 1 is the double-Abstract symptom even
    # if the stub text was reworded.
    abstract_headers = len(re.findall(r"(?mi)^\s*Abstract\s*$", head))
    if abstract_headers >= 2 and not findings:
        findings.append(
            "rendered PDF page 1 shows %d 'Abstract' headings (double-Abstract); "
            "the frontmatter stub abstract rendered above the real one" % abstract_headers
        )
    return {"valid": not findings, "findings": findings, "abstract_headers": abstract_headers}


def _validate_pdf_references_rendered(pdf_text: str, run_dir: Path) -> dict[str, object]:
    """When the bibliography is non-empty, the rendered PDF must contain an
    actually-populated References section (cause-agnostic: it does not matter
    WHICH internal step lost the citations - an empty rendered bibliography
    is undeliverable)."""
    bib = Path(run_dir) / "references.bib"
    if not bib.is_file():
        return {"valid": True, "findings": [], "bib_entries": 0}
    bib_entries = len(re.findall(r"@\w+\{", bib.read_text(encoding="utf-8", errors="ignore")))
    if bib_entries == 0:
        return {"valid": True, "findings": [], "bib_entries": 0}
    heading = re.search(r"(?mi)^\s*(?:references|bibliography)\s*$", pdf_text)
    if heading is None:
        return {
            "valid": False,
            "bib_entries": bib_entries,
            "entry_signals": 0,
            "findings": [
                "PDF has no References/Bibliography heading while references.bib "
                "holds %d entries; the bibliography did not render" % bib_entries
            ],
        }
    tail = pdf_text[heading.end():]
    entry_signals = len(re.findall(r"\b(?:19|20)\d{2}\b|doi[:.]|doi\.org", tail, flags=re.IGNORECASE))
    findings: list[str] = []
    required = min(bib_entries, 3)
    if entry_signals < required:
        findings.append(
            "References section renders empty or near-empty (%d entry signals after the "
            "heading) while references.bib holds %d verified entries; the body citations "
            "did not survive to the delivered PDF" % (entry_signals, bib_entries)
        )
    # E2E job v3_e9e1b75927a6: the bib held intact unicode names ('Maden,
    # Çağtay') but the rendered References showed 'Maden, .' - the render
    # chain dropped non-ASCII given names when abbreviating. Only the
    # rendered text can show this.
    dropped = sorted(set(re.findall(r"([A-Za-zÀ-ÿĀ-ž']+),\s+\.(?:,|\s)", tail)))
    if dropped:
        findings.append(
            "rendered References dropped author given-name initials for: %s "
            "(likely non-ASCII given names mangled during rendering); protect the "
            "initials in references.bib (e.g. brace the accented letters) so the "
            "rendered names are complete" % ", ".join(dropped[:5])
        )
    if findings:
        return {
            "valid": False,
            "bib_entries": bib_entries,
            "entry_signals": entry_signals,
            "findings": findings,
        }
    return {"valid": True, "findings": [], "bib_entries": bib_entries, "entry_signals": entry_signals}


def _validate_pdf_content_quality(text: str) -> dict[str, object]:
    findings: list[str] = []
    normalized = re.sub(r"\s+", " ", text or "").strip()
    fallback_hits = sum(
        normalized.lower().count(phrase)
        for phrase in (
            "for v3.2 production quality",
            "auditable bridge between the research contract and the available artifacts",
            "generated from verified run artifacts",
        )
    )
    low_quality_citations = re.findall(
        r"\(See,\s*[a-z](?:\s*,\s*[a-z]){1,}\)",
        normalized,
        flags=re.IGNORECASE,
    )
    addendum_count = len(re.findall(r"\bTraceability and Claim Discipline Addendum\b", text or ""))
    traceability_table_count = len(re.findall(r"(?m)^\s*\d+\.\s+Traceability Tables\b", text or ""))
    if fallback_hits >= 3:
        findings.append("PDF contains repeated fallback boilerplate")
    if low_quality_citations:
        findings.append("PDF contains low-quality citation labels")
    if addendum_count > 1 or traceability_table_count > 1:
        findings.append("PDF contains duplicated traceability addenda or tables")
    return {
        "valid": not findings,
        "fallback_boilerplate_hits": fallback_hits,
        "low_quality_citation_count": len(low_quality_citations),
        "traceability_addendum_count": addendum_count,
        "traceability_table_heading_count": traceability_table_count,
        "findings": findings,
    }


OVERFULL_HBOX_VISIBLE_PT = 5.0

# Caption claim tokens that require extracted/poolable effects to exist.
# Cause-agnostic at the claim level: any caption asserting these statistical
# objects is checked against the machine-produced real_results, mirroring
# claim<=evidence for body prose (2026-07-02: Figure 4 caption claimed a
# random-effects pooled estimate on a poolable_k=0 run).
CAPTION_EFFECT_CLAIM_TOKENS = (
    "pooled estimate",
    "pooled effect",
    "effect size",
    "random-effects",
    "meta-analytic estimate",
    "significant",
)


def _validate_render_log_overflow(run_dir: Path) -> dict[str, object]:
    """Consume the renderer's own Overfull \hbox report (ground truth) instead
    of trusting declared tbl-colwidths. Anything wider than
    OVERFULL_HBOX_VISIBLE_PT is a visible overlap; sub-threshold warnings are
    ordinary TeX noise."""
    log_path = run_dir / "paper_springer.log"
    if not log_path.is_file():
        return {"valid": True, "log_present": False, "overfull_count": 0, "findings": []}
    text = log_path.read_text(encoding="utf-8", errors="ignore")
    findings: list[str] = []
    count = 0
    for match in re.finditer(r"Overfull \\hbox \(([0-9.]+)pt too wide\)([^\n]*)", text):
        try:
            width = float(match.group(1))
        except ValueError:
            continue
        if width < OVERFULL_HBOX_VISIBLE_PT:
            continue
        count += 1
        findings.append(
            "render log reports visible Overfull \\hbox (%.1fpt too wide)%s"
            % (width, match.group(2).strip()[:80] and (" " + match.group(2).strip()[:80]))
        )
    return {
        "valid": not findings,
        "log_present": True,
        "overfull_count": count,
        "findings": findings,
    }


def _manuscript_figure_captions(run_dir: Path) -> list[tuple[str, str]]:
    """(source_file, caption) pairs from EVERY manuscript source. Sections are
    included because a caption fixed in the qmd re-infiltrates when Hermes
    recomposes from a stale section file (2026-07-03 round 5)."""
    sources = ["paper_draft_v0.qmd", "paper_springer.qmd"]
    sections_dir = run_dir / "sections"
    if sections_dir.is_dir():
        sources.extend(sorted("sections/%s" % p.name for p in sections_dir.glob("*.md")))
    captions: list[tuple[str, str]] = []
    for rel in sources:
        path = run_dir / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        captions.extend(
            (rel, m.group(1).strip()) for m in re.finditer(r"!\[([^\]]+)\]\(figures/", text)
        )
    return captions


def _validate_caption_claims(run_dir: Path) -> dict[str, object]:
    real_results = _read_json(run_dir / "real_experiments" / "real_results.json")
    synthesis = real_results.get("synthesis") if isinstance(real_results.get("synthesis"), dict) else {}
    effect_count = _int_review_value(synthesis.get("numeric_effect_count"), default=0)
    poolable = _int_review_value(real_results.get("max_poolable_k"), default=0)
    if max(effect_count, poolable) > 0:
        return {"valid": True, "findings": []}
    findings: list[str] = []
    negation_markers = (
        "no ", "not ", "0 ", "zero ", "without ", "deferred", "pending",
        "not estimated", "not pooled", "no pooled", "status",
    )
    for source, caption in _manuscript_figure_captions(run_dir):
        lowered = caption.lower()
        hits = [token for token in CAPTION_EFFECT_CLAIM_TOKENS if token in lowered]
        # An honest disclosure ("0 extracted effect sizes", "pooling deferred")
        # mentions the statistical object to DENY it; only affirmative claims
        # violate claim<=evidence.
        if hits and any(marker in lowered for marker in negation_markers):
            continue
        if hits:
            findings.append(
                "figure caption in %s claims %s but real_results has no extracted/poolable effects: %r"
                % (source, ", ".join(sorted(hits)), caption[:120])
            )
    return {"valid": not findings, "findings": findings}


CITATION_DUMP_PARAGRAPH_LIMIT = 8
CITATION_DUMP_SECTION_TITLES = ("bibliographic scope", "scope note", "citation note")


def _validate_citation_distribution(run_dir: Path) -> dict[str, object]:
    """No citation-dump sections. The dead-refs gate requires every bib entry
    cited IN CONTEXT; round 14 the writer invented an '8. Bibliographic Scope
    Note' section dumping ~40 citations in one paragraph to game the gate -
    a structure that does not exist in academic writing."""
    path = run_dir / "paper_draft_v0.qmd"
    if not path.is_file():
        return {"valid": True, "findings": []}
    text = path.read_text(encoding="utf-8", errors="ignore")
    findings: list[str] = []
    for match in re.finditer(r"(?m)^#{1,3}\s+(.+)$", text):
        title = match.group(1).strip().lower()
        if any(marker in title for marker in CITATION_DUMP_SECTION_TITLES):
            findings.append(
                "citation-dump section %r: remove it and distribute citations into the body sections"
                % match.group(1).strip()[:60]
            )
    for para in re.split(r"\n\s*\n", text):
        cites = len(re.findall(r"@[A-Za-z][\w:-]*", para))
        if cites > CITATION_DUMP_PARAGRAPH_LIMIT and "references.bib" not in para:
            findings.append(
                "paragraph packs %d citations (limit %d): distribute them into the sections they support"
                % (cites, CITATION_DUMP_PARAGRAPH_LIMIT)
            )
    return {"valid": not findings, "findings": findings}


def _cjk_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cjk = sum(1 for ch in letters if "\u4e00" <= ch <= "\u9fff")
    return cjk / len(letters)


def _validate_title_language(run_dir: Path) -> dict[str, object]:
    """The manuscript title must be in the manuscript's language. The title is
    copied from the b-side contract topic, which may be in the grill
    conversation's language (2026-07-02: Chinese title on an all-English
    manuscript)."""
    path = run_dir / "paper_draft_v0.qmd"
    if not path.is_file():
        return {"valid": True, "findings": []}
    text = path.read_text(encoding="utf-8", errors="ignore")
    title_match = re.search(r'(?m)^title:\s*"?([^"\n]+)"?', text)
    if not title_match:
        return {"valid": True, "findings": []}
    title = title_match.group(1)
    body = re.sub(r"(?s)\A---.*?---", "", text, count=1)
    title_cjk = _cjk_ratio(title)
    body_cjk = _cjk_ratio(body)
    mismatch = (title_cjk >= 0.5 and body_cjk < 0.1) or (title_cjk < 0.1 and body_cjk >= 0.5)
    if not mismatch:
        return {"valid": True, "findings": []}
    return {
        "valid": False,
        "findings": [
            "title language does not match manuscript body language "
            "(title CJK ratio %.2f vs body %.2f); translate the title into the manuscript language"
            % (title_cjk, body_cjk)
        ],
    }


_ABSTRACT_STUB_RE = re.compile(
    r"(?i)\b(?:pending|tbd|to be (?:written|added|completed)|placeholder|coming soon)\b"
)


def _frontmatter_abstract(front: str) -> str | None:
    """Return the frontmatter abstract text (inline or block scalar), or None
    when the frontmatter has no abstract key."""
    lines = front.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^abstract:\s*(.*)$", line)
        if m is None:
            continue
        inline = m.group(1).strip()
        if inline and inline not in ("|", ">", "|-", ">-", "|+", ">+"):
            return inline
        block: list[str] = []
        for follow in lines[i + 1:]:
            if not follow.strip():
                continue
            if re.match(r"^\s{2,}\S", follow):
                block.append(follow.strip())
            else:
                break
        return " ".join(block).strip()
    return None


def _validate_frontmatter_stub(run_dir: Path) -> dict[str, object]:
    """Fresh E2E job v3_e9e1b75927a6: page 1 rendered TWO Abstract blocks -
    the frontmatter stub 'Abstract pending.' above the real abstract. The
    render-gate placeholder list never covered stub abstracts."""
    findings: list[str] = []
    for name in ("paper_draft_v0.qmd", "paper_springer.qmd"):
        path = run_dir / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        front = re.match(r"(?s)\A---(.*?)---", text)
        if not front:
            continue
        abstract_text = _frontmatter_abstract(front.group(1))
        if abstract_text is None:
            continue
        if (
            abstract_text == ""
            or (_ABSTRACT_STUB_RE.search(abstract_text) and len(abstract_text) < 120)
        ):
            findings.append(
                "frontmatter abstract in %s is a placeholder stub (%r); write the real "
                "abstract into the frontmatter so the title page does not render a stub "
                "Abstract block above the real one" % (name, abstract_text[:60])
            )
    return {"valid": not findings, "findings": findings}


def _validate_bib_author_integrity(run_dir: Path) -> dict[str, object]:
    """CrossRef name-parse wreckage must not reach the rendered References:
    'Unknown, 2021', 'Maden, .' (empty given name) shipped in E2E job
    v3_e9e1b75927a6. Full-author-name rule (feedback_paper_pipeline_v2) now
    mechanically enforced."""
    bib = run_dir / "references.bib"
    if not bib.is_file():
        return {"valid": True, "findings": []}
    text = bib.read_text(encoding="utf-8", errors="ignore")
    findings: list[str] = []
    for match in re.finditer(r"@\w+\{([^,\s]+),(.*?)(?=@\w+\{|\Z)", text, flags=re.DOTALL):
        key, body = match.group(1), match.group(2)
        author = re.search(r"author\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n", body, flags=re.DOTALL)
        if not author:
            continue
        value = " ".join(author.group(1).split())
        problems = []
        if re.search(r"(?i)\bunknown\b|\banonymous\b", value):
            problems.append("author is Unknown/Anonymous")
        if re.search(r"\w+,\s*\.(?:\s|$|,)", value) or re.search(r"^\s*,|,\s*and\s+and\b", value):
            problems.append("empty or broken given-name initial")
        if problems:
            findings.append(
                "bib entry %s has a broken author field (%s): fix the author names "
                "from the source record or drop the entry" % (key, "; ".join(problems))
            )
        if len(findings) >= 6:
            break
    return {"valid": not findings, "findings": findings}


def _validate_inline_heading_leakage(run_dir: Path) -> dict[str, object]:
    """Markdown headings must start their own line. v3_0f6a0c83f9cf composed
    section headings onto the tail of paragraph lines ('... conclusion.
    ## Related Work'), so the rendered PDF showed literal '## X' tokens
    mid-paragraph and no real section existed after Introduction. Both
    mechanical gates and a floor-84 Hermes review missed it."""
    findings: list[str] = []
    for name in ("paper_draft_v0.qmd", "paper_springer.qmd"):
        path = run_dir / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        body = re.sub(r"(?s)\A---.*?---", "", text, count=1)
        body = re.sub(r"(?ms)^```.*?^```", "", body)
        for match in re.finditer(r"(?m)^(?P<prefix>.*\S.*?)\s(?P<heading>#{1,4}\s+[A-Z][^#\n]{2,60})$", body):
            heading = match.group("heading").strip()
            findings.append(
                "inline heading leakage in %s: '%s' is glued to the end of a "
                "paragraph line; put the heading on its own line" % (name, heading[:60])
            )
    return {"valid": not findings, "findings": findings[:6]}


def _validate_citations_rendered(run_dir: Path) -> dict[str, object]:
    """A manuscript with a verified bibliography must actually cite it.
    v3_0f6a0c83f9cf shipped an empty References section and zero inline
    citations while 35 two-source-verified entries sat unused: the body
    named authors in prose without one @citekey, so citeproc rendered
    nothing. Dump-pattern checks cannot catch total absence."""
    bib = run_dir / "references.bib"
    qmd = run_dir / "paper_draft_v0.qmd"
    if not bib.is_file() or not qmd.is_file():
        return {"valid": True, "findings": []}
    bib_keys = set(re.findall(r"@\w+\{([^,\s]+),", bib.read_text(encoding="utf-8", errors="ignore")))
    if not bib_keys:
        return {"valid": True, "findings": []}
    body = re.sub(r"(?s)\A---.*?---", "", qmd.read_text(encoding="utf-8", errors="ignore"), count=1)
    cited = set(re.findall(r"@([A-Za-z][A-Za-z0-9_:.#$%&+?<>~/-]*)", body)) & bib_keys
    if cited:
        return {"valid": True, "findings": [], "cited_count": len(cited)}
    return {
        "valid": False,
        "cited_count": 0,
        "findings": [
            "no inline citations rendered: references.bib has %d verified entries "
            "but the manuscript body cites none of them (@citekey markers absent), "
            "so the References section renders empty; weave the verified entries "
            "into the body sections they support" % len(bib_keys)
        ],
    }


def _validate_table_widths(run_dir: Path) -> dict[str, object]:
    qmd = run_dir / "paper_springer.qmd"
    if not qmd.is_file():
        return {
            "table_count": 0,
            "tables": [],
            "valid": False,
            "findings": ["paper_springer.qmd missing; cannot validate table layout"],
        }
    text = qmd.read_text(encoding="utf-8", errors="ignore")
    findings = []
    tables = []
    for match in re.finditer(r"(?m)^:\s+.*?\{#tbl-([^}\s]+)([^}]*)\}", text):
        table_id = match.group(1)
        attrs = match.group(2) or ""
        width_match = re.search(r'tbl-colwidths="?\[([^\]]+)\]"?', attrs)
        if not width_match:
            findings.append("table %s missing tbl-colwidths" % table_id)
            tables.append({"id": table_id, "widths": [], "sum": 0})
            continue
        widths = []
        for token in re.split(r"[,\s]+", width_match.group(1).strip()):
            if not token:
                continue
            try:
                widths.append(int(float(token)))
            except ValueError:
                findings.append("table %s has non-numeric tbl-colwidths token: %s" % (table_id, token))
        total = sum(widths)
        if total != 100:
            findings.append("table %s tbl-colwidths sum to %s, expected 100" % (table_id, total))
        tables.append({"id": table_id, "widths": widths, "sum": total})
    if len(tables) < 2:
        findings.append("paper requires at least 2 real Quarto tables; found %d" % len(tables))
    return {
        "table_count": len(tables),
        "tables": tables,
        "valid": not findings,
        "findings": findings,
    }


def _run_text(command: list[str], *, timeout_s: int) -> str:
    if shutil.which(command[0]) is None:
        return ""
    try:
        return subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=timeout_s,
            check=False,
        ).stdout
    except Exception:
        return ""
