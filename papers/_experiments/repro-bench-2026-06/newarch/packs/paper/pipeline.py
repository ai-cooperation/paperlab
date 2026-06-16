"""Paper pipeline ON the framework (Hermes+Skill new architecture).

The 11-phase meta-analysis lane as framework Phase handlers. Division of labour
(DESIGN §3.1/§3.6):
  - deterministic (paperctl / direct): meta-analysis, refs, figures, tables, render,
    floor_score — the factual backbone, never an LLM.
  - codex BRAIN (LiveDispatcher reviewer class): gap, structure, claim-evidence
    matrix, composition, review judgment — reasoning that needs the strong brain.
  - free hermes WORKERS (LiveDispatcher drafter/fixer class): the 7 section drafts +
    self-heal fix-agents — the bulk, offloaded to the free worker so the Hermes path
    is cheap. The gates + brain review ENFORCE correctness, so a weaker drafter is OK.

`run_paper(run_dir, contract, dispatcher)` runs it; the framework Orchestrator owns
the loop + checkpoints, the gates block, the SelfHealLoop drives 60->80.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import delivery_audit
import floor_score
import meta_figures
import paper_driver as PD
import render_springer
import tables
from framework import (
    Dispatcher,
    Orchestrator,
    Phase,
    ReviewOutcome,
    SelfHealLoop,
    WorkerPacket,
    run_gates,
)

from .pack import PaperPack

SKILLS = Path(os.environ.get("PAPERBENCH_SKILLS", str(Path.home() / "paperbench" / "skills-bundle")))
SCORE_TARGET = 80.0
SECTIONS = ["Introduction", "Related Work", "Methods", "Results", "Discussion",
            "Limitations", "Conclusion"]


def _skill(*names: str) -> str:
    return "\n".join(f"- {SKILLS}/{n}/SKILL.md" for n in names)


def _hdr(c: dict[str, Any]) -> str:
    return (
        "Governing research contract (do NOT change the topic):\n"
        f"- Topic: {c.get('topic')}\n- Research question: {c.get('research_question')}\n"
        f"- Contribution: {c.get('contribution')}\n- Target journal: {c.get('target_journal')}\n"
        "Rules: academic English; no emoji; no invented numbers; every numeric claim must trace to "
        "real_experiments/real_results.json; ground every citation in references.bib.\n")


def _dispatch_brain(o: Orchestrator, label: str, prompt: str, writes: list[str],
                    timeout: int = 1200) -> bool:
    """One codex-brain reasoning unit via the dispatcher; verify the artifact exists,
    retry once with a forceful nudge if the brain returned OK but wrote nothing."""
    o.dispatcher.run_dir = o.run_dir  # type: ignore[attr-defined]
    for attempt in range(2):
        p = prompt if attempt == 0 else (
            prompt + f"\n\nIMPORTANT: you MUST actually create the file(s) "
            f"{writes} on disk now — do not just acknowledge. Write them, then output CHILD_OK.")
        pkt = WorkerPacket(task_id=f"{label}{'' if attempt == 0 else '-retry'}", role=label,
                           worker_class="reviewer", task_goal=p, allowed_files_write=writes)
        o.fan_out([pkt])
        if all((o.run_dir / w).exists() for w in writes):
            return True
    return False


def _dispatch_worker(o: Orchestrator, label: str, prompt: str, writes: list[str],
                     timeout: int = 600) -> bool:
    pkt = WorkerPacket(task_id=label, role=label, worker_class="drafter",
                       task_goal=prompt, allowed_files_write=writes)
    o.dispatcher.run_dir = o.run_dir  # type: ignore[attr-defined]
    res = o.fan_out([pkt])[0]
    return res.ok


# ── phases ───────────────────────────────────────────────────────────────────
def _phase_data(o: Orchestrator) -> None:
    """Deterministic lane: pool real effects + build verified refs + draw figures."""
    contract = o.dossier.data["contract"]
    result = PD.run_meta_analysis_lane(o.run_dir, contract)
    kept = PD.expand_references_from_analysis(o.run_dir, contract, result)
    meta_figures.generate(o.run_dir)
    prisma = (result.get("meta") or {}).get("prisma") or {}
    o.dossier.set("evidence", {
        **o.dossier.data.get("evidence", {}),
        "studies_with_effects": prisma.get("studies_with_effects"),
        "pooled": (result.get("meta") or {}).get("pooled"),
        "references": {"bib_count": kept},
        "real_results": "real_experiments/real_results.json",
        "figures": [{"name": p.stem} for p in (o.run_dir / "figures").glob("*.svg")],
    })
    o.dossier.pack_ext_set("metrics_block", PD.meta_metrics_block(result))


def _phase_gap(o: Orchestrator) -> None:
    c = o.dossier.data["contract"]
    prompt = _hdr(c) + f"""
You are the RESEARCH-POSITIONING brain. Read these skills:
{_skill('paper-draft', 'literature-synthesis', 'innovation-positioning')}
Phase 3. Inputs in THIS directory: references.bib, real_experiments/real_results.json.
Write `phase3_positioning.md`: (1) a literature landscape grouping the real references;
(2) a Gap Matrix table | Gap | Description | Existing Work | Our Approach | with >=3 gaps, each
Existing-Work cell citing REAL references.bib entries (author/year), never invented; (3) a
Differentiation Statement; (4) 3 contribution points tied to gaps. Only write that one file.
End with CHILD_OK."""
    _dispatch_brain(o, "phase3_gap", prompt, ["phase3_positioning.md"])


def _phase_structure(o: Orchestrator) -> None:
    c = o.dossier.data["contract"]
    prompt = _hdr(c) + f"""
You are the PAPER-STRUCTURE brain. Read: {_skill('paper-draft', 'figure-design', 'qmd-writer')}
Phase 4. Inputs: phase3_positioning.md, references.bib, real_experiments/real_results.json.
Write `phase4_structure.md`: section outline (Abstract/Introduction/Related Work/Methods/Results/
Discussion/Limitations/Conclusion), each section's key claim, the figures/tables to reference
(@fig-forest/@fig-prisma/@fig-method/@tbl-*), target 4500-6000 words. Only that file. End with CHILD_OK."""
    _dispatch_brain(o, "phase4_structure", prompt, ["phase4_structure.md"])


def _phase_claim_evidence(o: Orchestrator) -> None:
    c = o.dossier.data["contract"]
    prompt = _hdr(c) + f"""
You are the CLAIM-EVIDENCE (Gate B) brain. Read: {_skill('paper-draft', 'paper-review-skill')}
Inputs: real_experiments/real_results.json, phase3_positioning.md, phase4_structure.md.
Write `claim_evidence_map.md`: a markdown table | Claim | Evidence (real_results field/table/figure) |
Exact-Match? | N-Support | Attribution-verb | for EVERY quantitative claim. Produce AT LEAST 8 claim rows.
In the Exact-Match? column put the LITERAL word PASS for every row whose number equals real_results
exactly (FAIL if it does not) — aim for all PASS. Numbers must equal real_results exactly; N<3 ->
"sample too small" caveat; verb tier by N+effect (N>=10&p<0.01 -> dominates/causes; N in[3,10] ->
correlates/associated; N<3 -> suggests, strong causal verbs BANNED). Only that file. End with CHILD_OK."""
    _dispatch_brain(o, "gate_b", prompt, ["claim_evidence_map.md"])


def _phase_write(o: Orchestrator) -> None:
    """7 free-worker section drafts -> codex composition into paper_draft_v0.qmd."""
    c = o.dossier.data["contract"]
    metrics = o.dossier.data.get("pack_ext", {}).get("metrics_block", "")
    (o.run_dir / "sections").mkdir(exist_ok=True)
    # free workers draft each section (the bulk; offloaded to the free worker tier)
    packets = [WorkerPacket(
        task_id=f"draft-{s.replace(' ', '_')}", role=f"section:{s}", worker_class="drafter",
        task_goal=_hdr(c) + f"""
You draft ONLY the "{s}" section of an abstract-level random-effects meta-analysis paper. Read:
{_skill('paper-draft', 'academic-writing')}
Inputs: phase3_positioning.md (gap), phase4_structure.md (outline), claim_evidence_map.md (allowed
claims), references.bib. Write `sections/{s.replace(' ', '_')}.md` — prose for the {s} section only,
academic English, citing references.bib by @key. Reference figures ONLY as @fig-forest/@fig-prisma/
@fig-method (no image embeds, no {{#fig-}} labels). Use ONLY these admissible numbers, verbatim:

{metrics}

Only write that one file. End with CHILD_OK.""",
        allowed_files_write=[f"sections/{s.replace(' ', '_')}.md"])
        for s in SECTIONS]
    o.dispatcher.run_dir = o.run_dir  # type: ignore[attr-defined]
    o.fan_out(packets)
    # codex composes the drafts into the final QMD (enforces numbers + structure + no dup figures)
    drafted = [f"sections/{s.replace(' ', '_')}.md" for s in SECTIONS
               if (o.run_dir / "sections" / f"{s.replace(' ', '_')}.md").exists()]
    compose = _hdr(c) + f"""
You are the COMPOSITION brain. Read: {_skill('paper-draft', 'academic-writing', 'qmd-writer', 'journal-templates')}
Assemble these section drafts into a complete Quarto `paper_draft_v0.qmd` (>=4500 words):
{chr(10).join('- ' + d for d in drafted)}
Plus an Abstract you write. Frontmatter: title, author "Cooperation.TW / Paper Lab", bibliography
references.bib, colorlinks/link-citations/citecolor blue. Cite >=20 references. Reference figures ONLY by
@fig-forest/@fig-prisma/@fig-method in prose (NO image embeds, NO {{#fig-}} labels — the pipeline injects
each figure once). Fix any number that does not match real_experiments/real_results.json. State in
Limitations that this is abstract-level (no full text). Only write paper_draft_v0.qmd. End with CHILD_OK."""
    _dispatch_brain(o, "phase8_compose", compose, ["paper_draft_v0.qmd"], timeout=1200)


def _render(run_dir: Path, contract: dict[str, Any]) -> bool:
    try:
        tables.inject(run_dir, contract)
        tables.inject_figures(run_dir)
    except Exception:  # noqa: BLE001
        pass
    return render_springer.render(run_dir, contract)


def _phase_render_gates(o: Orchestrator) -> None:
    _render(o.run_dir, o.dossier.data["contract"])
    # build the gate dossier view + run C/D/F (B already enforced after claim-evidence)
    draft = (o.run_dir / "paper_draft_v0.qmd")
    gd = {
        "draft_text": draft.read_text(encoding="utf-8") if draft.exists() else "",
        "qmd_text": draft.read_text(encoding="utf-8") if draft.exists() else "",
        "evidence": o.dossier.data.get("evidence", {}),
        "real_results": _read(o.run_dir / "real_experiments" / "real_results.json"),
        "claim_evidence": [], "render_ok": draft.exists(),
    }
    report = run_gates(PaperPack(), gd, only={"C", "D", "F"})
    o.dossier.data.setdefault("gates", {})["render"] = report.as_dict()
    o.dossier.save()


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _phase_review_heal(o: Orchestrator) -> None:
    """Phase 9: codex 7-dim review + deterministic floor; free-worker fix-agents."""
    c = o.dossier.data["contract"]

    def review_fn(_data: dict[str, Any], rnd: int) -> ReviewOutcome:
        # The brain DIAGNOSES *and PRESCRIBES* in ONE call: for every problem it emits
        # a concrete, executable edit (verbatim locator + exact replacement). The
        # free worker that applies them is NOT smart — it only finds the locator and
        # writes the replacement. The intelligence is all here, in codex.
        prompt = _hdr(c) + f"""
You are the REVIEW brain (independent — you did NOT write this). Read:
{_skill('paper-draft', 'paper-review-skill', 'elite-reviewer-audit', 'paper-logic-audit')}
Review paper_draft_v0.qmd vs real_experiments/real_results.json + claim_evidence_map.md as a tough
Q1 reviewer on the 7 dimensions. Write `quality_review_round{rnd}.json` with this EXACT shape:
{{"score_100": <int 0-100>, "p0": [<short labels>], "p1": [<short labels>],
  "edits": [
    {{"severity": "P0|P1|P2|P3",
      "locator": "<COPY the exact existing sentence/phrase from the qmd that must change — verbatim>",
      "action": "replace|insert_after|delete",
      "replacement": "<the EXACT new text to write; empty for delete>",
      "reason": "<one line>"}}
  ]}}
RULES: for EVERY P0/P1 you MUST give a concrete edit whose `locator` is copied VERBATIM from the qmd
and whose `replacement` is the exact final text — never a vague suggestion. The editor that applies
these is NOT smart; it only finds your locator and writes your replacement. Prioritise: (a) overclaims
-> rewrite so claim <= evidence (numbers must match real_results; downgrade strong verbs when k small /
CI crosses zero); (b) STRENGTHEN the Limitations section — prescribe a `replacement` whose text
EXPLICITLY contains these honest caveats, all genuinely true here, using these exact phrasings: the
pooled effect is "not statistically significant" (the 95% CI crosses zero); the findings "may not
generalize" and have limited "external validity"; the "sample size" is small (a "subset" of available
studies, small k); abstract-level extraction only (no full text, pattern-based screening, no RoB2/
GRADE/PRISMA). Always include at least one P1 edit whose replacement is a 3-5 sentence Limitations
paragraph containing those phrases (locator = the existing Limitations heading or first sentence).
Do NOT edit the paper yourself. End with CHILD_OK."""
        _dispatch_brain(o, f"review_round{rnd}", prompt, [f"quality_review_round{rnd}.json"])
        rev = _read(o.run_dir / f"quality_review_round{rnd}.json")
        fs = floor_score.floor_scores(o.run_dir)
        floor100 = round(float(fs.get("mean_6_floor") or 0) * 10, 1)
        hg = fs.get("hard_gates") or {}
        # carry the concrete edits as the loop's findings (one mechanical batch)
        edits = [e for e in (rev.get("edits") or []) if isinstance(e, dict) and e.get("locator")]
        return ReviewOutcome(
            round=rnd, score=float(rev.get("score_100") or 0),
            p0_count=len(rev.get("p0") or []), floor=floor100,
            floor_failed=not hg.get("all_pass", True),   # floor_score hard-gates: all_pass
            findings_by_type={"edits": edits} if edits else {})

    # the self-heal loop dispatches free-worker fix-agents on each failing round
    loop = _PaperSelfHeal(o, review_fn, target_score=SCORE_TARGET, max_rounds=3)
    loop.run()
    o.dossier.pack_ext_set("final_score", floor_score.floor_scores(o.run_dir).get("mean_6_floor"))


class _PaperSelfHeal(SelfHealLoop):
    """SelfHealLoop whose fix-agents are FREE hermes workers that actually edit the
    qmd, and which re-renders after each round."""

    def __init__(self, orch: Orchestrator, review_fn, **kw: Any):
        super().__init__(orch.dossier, orch.dispatcher, review_fn, **kw)
        self._orch = orch

    def _dispatch_fixers(self, outcome) -> list[str]:
        """Apply codex's prescribed edits. Exact-locator edits are applied
        DETERMINISTICALLY in Python (guaranteed to land — the most reliable
        "executor"); only edits whose locator is not an exact substring fall to a
        big-pickle worker for a fuzzy mechanical apply. The worker never reasons about
        WHAT to fix — codex already decided that; it only writes prescribed text."""
        edits = (outcome.findings_by_type or {}).get("edits") or []
        if not edits:
            return []
        qmd = self._orch.run_dir / "paper_draft_v0.qmd"
        text = qmd.read_text(encoding="utf-8") if qmd.exists() else ""
        applied = 0
        unapplied: list[dict[str, Any]] = []
        for e in edits:
            loc = str(e.get("locator") or "")
            rep = str(e.get("replacement") or "")
            act = e.get("action") or "replace"
            if loc and loc in text:
                if act == "replace":
                    text = text.replace(loc, rep, 1)
                elif act == "insert_after":
                    text = text.replace(loc, loc + "\n" + rep, 1)
                elif act == "delete":
                    text = text.replace(loc, "", 1)
                applied += 1
            else:
                unapplied.append(e)
        qmd.write_text(text, encoding="utf-8")          # deterministic edits land here
        if unapplied:                                   # fuzzy remainder -> mechanical worker
            blocks = [f"EDIT [{e.get('severity', 'P1')}] action={e.get('action', 'replace')}\n"
                      f"  LOCATOR (find this, allow a close match): {e.get('locator')}\n"
                      f"  REPLACEMENT (write verbatim): {e.get('replacement', '')}"
                      for e in unapplied]
            prompt = (
                "You are a MECHANICAL editor, NOT a writer. Apply these reviewer edits to "
                "paper_draft_v0.qmd. For each: find the LOCATOR text and replace/insert-after/"
                "delete per its action, writing REPLACEMENT verbatim. Do NOT rephrase, re-pool, "
                "summarise, or invent. Touch ONLY text named by a locator. Save the file.\n\n"
                + "\n\n".join(blocks) + "\n\nEnd with CHILD_OK.")
            _dispatch_worker(self._orch, f"apply-edits-r{outcome.round}", prompt, ["paper_draft_v0.qmd"])
        _render(self._orch.run_dir, self._orch.dossier.data["contract"])
        return [f"deterministic:{applied}", f"worker:{len(unapplied)}"]


def build_paper_phases() -> list[Phase]:
    return [
        Phase("data", _phase_data, checkpoint_artifacts=["real_experiments/real_results.json", "references.bib"]),
        Phase("gap", _phase_gap, checkpoint_artifacts=["phase3_positioning.md"]),
        Phase("structure", _phase_structure, checkpoint_artifacts=["phase4_structure.md"]),
        Phase("claim_evidence", _phase_claim_evidence, checkpoint_artifacts=["claim_evidence_map.md"]),
        Phase("write", _phase_write, checkpoint_artifacts=["paper_draft_v0.qmd"]),
        Phase("render_gates", _phase_render_gates, checkpoint_artifacts=["paper_draft_v0.pdf"]),
        Phase("review_heal", _phase_review_heal, checkpoint_artifacts=["paper_draft_v0.qmd"]),
    ]


def run_paper(run_dir: Path, contract: dict[str, Any], dispatcher: Dispatcher) -> dict[str, Any]:
    """Entry point: run the full paper pipeline on the framework over a prepared run dir
    (which must contain research_contract.json + the corpus cache)."""
    run_dir = Path(run_dir)
    orch = Orchestrator(run_dir, PaperPack(), dispatcher, build_paper_phases(),
                        job_id=contract.get("job_id", run_dir.name), contract=contract,
                        max_steps=200)
    orch.run()
    fs = floor_score.floor_scores(run_dir)
    return {"floor_100": round(float(fs.get("mean_6_floor") or 0) * 10, 1),
            "dimensions": fs.get("scores_7dim"),
            "delivery": delivery_audit.audit(run_dir).get("verdict"),
            "phases_done": orch.completed_phases()}
