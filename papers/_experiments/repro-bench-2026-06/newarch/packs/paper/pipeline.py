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
import format_repair
import meta_figures
import paper_driver as PD
from framework import (
    Dispatcher,
    Orchestrator,
    OrchestratorBlocked,
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


def _framing_block(c: dict[str, Any]) -> str:
    """The researcher's intellectual framing from the b-side grill (gap / positioning /
    candidate claims). The a-side must BUILD ON this — not regenerate the positioning
    blind from references.bib (the discourse defect). Framing is the starting HYPOTHESIS;
    real_results + the claim<=evidence gate are the REFEREE: any claim the evidence does
    not support is downgraded or dropped, so honoring the human's angle never becomes an
    overclaim."""
    fr = c.get("framing") or {}
    gap = str(fr.get("gap") or "").strip()
    pos = str(fr.get("positioning") or "").strip()
    claims = [str(x).strip() for x in (fr.get("claims") or []) if str(x).strip()]
    if not (gap or pos or claims):
        return ""
    out = ["\nResearcher framing (BUILD ON and REFINE this; ground it in references.bib + "
           "real_results; DROP any element the evidence does not support — claim never exceeds evidence):"]
    if gap:
        out.append(f"- Gap: {gap}")
    if pos:
        out.append(f"- Positioning: {pos}")
    if claims:
        out.append("- Candidate claims (each must map to a real_results row or be downgraded/dropped):")
        out += [f"    * {x}" for x in claims]
    return "\n".join(out) + "\n"


def _hdr(c: dict[str, Any]) -> str:
    return (
        "Governing research contract (do NOT change the topic):\n"
        f"- Topic: {c.get('topic')}\n- Research question: {c.get('research_question')}\n"
        f"- Contribution: {c.get('contribution')}\n- Target journal: {c.get('target_journal')}\n"
        "Rules: academic English; no emoji; no invented numbers; every numeric claim must trace to "
        "real_experiments/real_results.json; ground every citation in references.bib.\n"
        + _framing_block(c))


def _dispatch_brain(o: Orchestrator, label: str, prompt: str, writes: list[str],
                    timeout: int = 1200, worker_fallback: bool = True) -> bool:
    """One codex-brain reasoning unit via the dispatcher; verify the artifact exists,
    retry once with a forceful nudge if the brain returned OK but wrote nothing.

    DEGRADATION LADDER: if codex is UNAVAILABLE (usage limit / quota), don't crash the
    whole run — fall back to the FREE worker (big-pickle) to finish the task. The output
    is lower quality (and the deterministic floor will reflect that), but the run COMPLETES
    and delivers instead of being stuck with no output. The degradation is recorded."""
    o.dispatcher.run_dir = o.run_dir  # type: ignore[attr-defined]
    for attempt in range(2):
        p = prompt if attempt == 0 else (
            prompt + f"\n\nIMPORTANT: you MUST actually create the file(s) "
            f"{writes} on disk now — do not just acknowledge. Write them, then output CHILD_OK.")
        pkt = WorkerPacket(task_id=f"{label}{'' if attempt == 0 else '-retry'}", role=label,
                           worker_class="reviewer", task_goal=p, allowed_files_write=writes)
        res = o.fan_out([pkt])[0]
        if all((o.run_dir / w).exists() for w in writes):
            return True
        if res.status == "error":          # codex unavailable (usage limit / quota)
            if worker_fallback and _worker_fallback(o, label, p, writes):
                return True                # big-pickle finished it (degraded) — run continues
            raise OrchestratorBlocked(label, reason=f"brain unavailable at {label}: {'; '.join(res.blockers)}")
    # the brain ran but wrote no output (twice) -> last-resort free-worker fallback, else block
    if worker_fallback and _worker_fallback(o, label, prompt, writes):
        return True
    raise OrchestratorBlocked(label, reason=f"brain produced no output at {label} after 2 attempts: {writes}")


def _worker_fallback(o: Orchestrator, label: str, prompt: str, writes: list[str]) -> bool:
    """codex (brain) unavailable -> the FREE worker (big-pickle) finishes the task so the
    run completes (lower quality, never stuck). Records the degradation in the dossier."""
    pkt = WorkerPacket(task_id=f"{label}-fallback", role=label, worker_class="drafter",
                       task_goal=prompt, allowed_files_write=writes)
    o.dispatcher.run_dir = o.run_dir  # type: ignore[attr-defined]
    o.fan_out([pkt])
    if all((o.run_dir / w).exists() for w in writes):
        o.dossier.data.setdefault("degraded", []).append(
            {"phase": label, "reason": "codex usage limit -> big-pickle fallback (lower quality)"})
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
def _is_dataset_lane(contract: dict[str, Any]) -> bool:
    """A real-data analysis (not literature/meta) of an arbitrary public dataset that is
    NOT the registered HUPD lane -> the general agent-driven dataset lane."""
    ds = contract.get("data_source") or {}
    name = str(ds.get("name") or "").lower()
    return str(ds.get("type") or "").lower() == "dataset" and "hupd" not in name


def _phase_data(o: Orchestrator) -> None:
    """Phase 1 (data): dispatch by data_source.type. meta/literature -> the deterministic
    OpenAlex lane; an arbitrary public DATASET -> the general agent-driven dataset lane."""
    contract = o.dossier.data["contract"]
    if _is_dataset_lane(contract):
        _phase_data_dataset(o, contract)
    else:
        _phase_data_meta(o, contract)


def _phase_data_meta(o: Orchestrator, contract: dict[str, Any]) -> None:
    """Deterministic lane: pool real effects + build verified refs + draw figures."""
    result = PD.run_meta_analysis_lane(o.run_dir, contract)
    kept = PD.expand_references_from_analysis(o.run_dir, contract, result)
    meta_figures.generate(o.run_dir)
    prisma = (result.get("meta") or {}).get("prisma") or {}
    o.dossier.set("evidence", {
        **o.dossier.data.get("evidence", {}),
        "studies_with_effects": prisma.get("studies_with_effects"),
        "pooled": (result.get("meta") or {}).get("pooled"),
        "references": {"bib_count": kept, "doi_real_rate": _doi_real_rate(o.run_dir)},
        "real_results": "real_experiments/real_results.json",
        "figures": [{"name": p.stem} for p in (o.run_dir / "figures").glob("*.svg")],
    })
    o.dossier.pack_ext_set("metrics_block", PD.meta_metrics_block(result))


REF_FLOOR = 35    # the paper-draft skill's HARD minimum real, verified references


def _build_dataset_references(o: Orchestrator, contract: dict[str, Any],
                              lit: dict[str, Any]) -> int:
    """Multi-source, CrossRef-verified related-work bibliography for the dataset lane.

    DISCOVERY is multi-source: the BRAIN (codex) generates a topic reading list (broad
    real knowledge of the field) AND the OpenAlex corpus seeds real on-topic DOIs — NOT
    OpenAlex alone (the single-source cause of the 14-ref thinness). Semantic Scholar is
    deliberately skipped (rate-limited, unreliable).

    VERIFICATION is fail-closed and runs on the WHOLE list AFTER it is assembled (skill
    Layer 1): refs_llm CrossRef-title-verifies each codex candidate, and then EVERY DOI
    (codex + OpenAlex seed + contract seed) is routed through build_refs_from_doi_list,
    which CrossRef-verifies by DOI and DROPS anything fabricated. So no reference enters
    the bibliography that CrossRef has not confirmed real — supplementing references ALWAYS
    re-runs CrossRef. Targets a buffer above REF_FLOOR so the DOI re-verify drop still
    nets >= REF_FLOOR."""
    import dataset_lane.refs_llm as refs_llm
    analysis = (lit or {}).get("analysis") or {}
    seed = [{"doi": w.get("doi"), "title": w.get("title"), "year": w.get("year")}
            for w in (analysis.get("background_works") or analysis.get("most_cited") or [])
            if w.get("doi")]
    topic = PD._literature_query(contract)
    disc = refs_llm.collect(
        o.run_dir, topic,
        lambda p, wr: _dispatch_brain(o, "ref_discovery", p, wr, worker_fallback=False),
        target=REF_FLOOR + 12, seed_dois=seed)
    o.dossier.data.setdefault("ref_discovery", {}).update(
        {"requested": disc["requested"], "verified_candidates": disc["verified"], "rounds": disc["rounds"]})
    # Layer 1 re-verify: the FULL union of DOIs (codex + OpenAlex + contract) through the
    # CrossRef DOI-verify bib builder (writes references.bib / metadata.json / doi_audit.json).
    union: dict[str, dict[str, Any]] = {}
    for c in PD.contract_doi_candidates(contract):
        d = str(c.get("doi") or "").strip().lower()
        if d:
            union[d] = {"doi": d}
    for r in disc["refs"]:
        union.setdefault(r["doi"], {"doi": r["doi"]})
    audit = PD.build_refs_from_doi_list(o.run_dir, list(union.values()))
    kept = int(audit.get("kept") or 0)
    # fail-closed floor (the skill's HARD >=35): never write a paper on a thin bibliography.
    if kept < REF_FLOOR:
        raise OrchestratorBlocked("data", reason=(
            f"references below the skill floor: {kept} CrossRef-verified < {REF_FLOOR} "
            f"(codex discovery {disc['rounds']} round(s) + OpenAlex seed exhausted; "
            "topic may be too narrow)"))
    return kept


def _phase_data_dataset(o: Orchestrator, contract: dict[str, Any]) -> None:
    """General dataset lane: the agent FETCHES the real data + WRITES+RUNS the analysis;
    deterministic gates verify (no hallucination); then related-work refs come from a topic
    literature search (the dataset gives the result, the literature gives the context)."""
    import dataset_lane

    def brain(prompt: str, writes: list[str]) -> bool:
        return _dispatch_brain(o, "dataset_brain", prompt, writes)

    def worker(prompt: str, writes: list[str]) -> bool:
        return _dispatch_worker(o, "dataset_worker", prompt, writes)

    skills = _skill("dataset-fetch", "survey-weighted-analysis", "number-trace-writing")
    res = dataset_lane.lane.run(o.run_dir, contract, brain=brain, worker=worker, skills=skills)
    # Self-upgrade SKILL loop: distil this run's failures into a general skill lesson so the
    # next run avoids them (the "Skill" half of Hermes+Skill). Best-effort, never blocks.
    try:
        learned = dataset_lane.skill_upgrade.distill_and_persist(
            o.run_dir, res.get("history") or [], contract, brain=brain, bundle_dir=SKILLS)
        if learned:
            o.dossier.data.setdefault("learned", []).append(learned)
    except Exception:  # noqa: BLE001
        pass
    if not res.get("ok"):
        reasons = "; ".join(p.get("description", "") for p in (res.get("problems") or [])[:3])
        raise OrchestratorBlocked("data", reason=f"dataset lane blocked ({res.get('stage')}): {reasons}")

    # related-work bibliography from a topic literature search (NOT from the dataset).
    # CRITICAL: openalex_analysis.run writes its OWN real_experiments/real_results.json
    # (a scientometric result) — it would CLOBBER the dataset analysis result. Snapshot +
    # restore around it so the dataset's real_results (the paper's numbers) survives.
    rr_path = o.run_dir / "real_experiments" / "real_results.json"
    saved = rr_path.read_text(encoding="utf-8") if rr_path.is_file() else None
    try:
        import openalex_analysis
        lit = openalex_analysis.run(PD._literature_query(contract), o.run_dir)
    except Exception:  # noqa: BLE001 - no corpus just means codex-discovery-only bibliography
        lit = {}
    if saved is not None:
        rr_path.write_text(saved, encoding="utf-8")   # restore the dataset analysis result
    kept = _build_dataset_references(o, contract, lit)

    # Deterministic figures from the analysis output: a forest of model coefficients, a
    # spline dose-response, and the sample-construction flow — machine-drawn so a figure
    # can never disagree with the numbers (the sibling of meta_figures for this lane).
    # General: keyed off the GENERIC real_results schema (models[]/spline/sample_flow),
    # zero dataset-specific strings. The review loop no longer has to invent text-box
    # placeholders for absent figures (the defect that capped this lane's floor).
    import dataset_lane.figures as ds_figures
    ds_figures.generate(o.run_dir)

    rr = res.get("real_results") or {}
    o.dossier.set("evidence", {
        **o.dossier.data.get("evidence", {}),
        "lane": "dataset_agent_analysis",
        "dataset_models": rr.get("models"),
        "survey_design": rr.get("survey_design"),
        "sample_flow": rr.get("sample_flow"),
        "references": {"bib_count": kept, "doi_real_rate": _doi_real_rate(o.run_dir)},
        "real_results": "real_experiments/real_results.json",
        "figures": [{"name": p.stem} for p in (o.run_dir / "figures").glob("*.svg")],
    })
    o.dossier.pack_ext_set("metrics_block", dataset_lane.lane.metrics_block(rr))


def _phase_gap(o: Orchestrator) -> None:
    c = o.dossier.data["contract"]
    prompt = _hdr(c) + f"""
You are the RESEARCH-POSITIONING brain. Read these skills:
{_skill('paper-draft', 'literature-synthesis', 'innovation-positioning')}
Phase 3. Inputs: references.bib, real_experiments/real_results.json, AND the Researcher framing above.
ANCHOR the positioning in the Researcher framing — validate and sharpen its gap and claims against
references.bib + real_results; keep what they support, refine/drop what they do not. Do NOT regenerate
a positioning that ignores the framing.
Write `phase3_positioning.md`: (1) a literature landscape grouping the real references;
(2) a Gap Matrix table | Gap | Description | Existing Work | Our Approach | with >=3 gaps, each
Existing-Work cell citing REAL references.bib entries (author/year), never invented; (3) a
Differentiation Statement; (4) 3 contribution points tied to gaps. Only write that one file.
End with CHILD_OK."""
    _dispatch_brain(o, "phase3_gap", prompt, ["phase3_positioning.md"])
    # Store STRUCTURED gaps in the dossier now (the robust path): the projection reads a
    # structured field instead of re-parsing markdown at request time. Parsed once,
    # deterministically; never blocks the run if the format drifts.
    try:
        from . import gaps as _gaps
        md = (o.run_dir / "phase3_positioning.md").read_text(encoding="utf-8", errors="ignore")
        parsed = _gaps.parse_gap_matrix(md)
        if parsed:
            o.dossier.set("claims", {**o.dossier.data.get("claims", {}), "research_gaps": parsed})
            o.dossier.save()
    except Exception:  # noqa: BLE001 - gap projection is best-effort, never fail the phase
        pass


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


def _fig_hint(o: Orchestrator, c: dict[str, Any]) -> str:
    """The exact `@fig-*` refs the writer may use — lane-aware AND limited to figures that
    were actually produced (figures are drawn in the data phase, before writing), so the
    writer never references a figure the analysis did not generate."""
    import tables
    refs = tables.available_fig_refs(o.run_dir, tables.figspec_for(c))
    return "/".join(refs) if refs else "@fig-forest"


def _paper_kind(c: dict[str, Any]) -> str:
    """Lane-aware description of WHAT is being written, so the meta-analysis framing
    (and its abstract-level/PRISMA limitations) does not leak into a dataset study."""
    return ("an empirical study analysing a public dataset with the documented real results"
            if _is_dataset_lane(c) else "an abstract-level random-effects meta-analysis paper")


def _limitations_hint(c: dict[str, Any]) -> str:
    """The honest limitation framing for the lane (meta = abstract-level screening; dataset
    = observational/associational), so the writer states caveats that are actually true."""
    return ("the design is observational and the estimates are associational, not causal"
            if _is_dataset_lane(c) else "this is abstract-level (no full text)")


def _limitations_caveats(c: dict[str, Any]) -> str:
    """The EXACT honest-caveat phrasings the review brain must put in Limitations — lane
    aware, so a dataset study does not get meta-analysis caveats (RoB2/GRADE/PRISMA) that
    are not true of it, and a meta-analysis does not get panel caveats."""
    if _is_dataset_lane(c):
        return ('the design is "observational" and the estimates are "associational, not '
                'causal"; the findings "may not generalize" and have limited "external '
                'validity"; the analytic sample is a harmonized "subset" of available '
                'country-year data with small-k subgroups; the panel is "unweighted" and the '
                'variables are broad "aggregate indicators" that do not identify a mechanism')
    return ('the pooled effect is "not statistically significant" (the 95% CI crosses zero); '
            'the findings "may not generalize" and have limited "external validity"; the '
            '"sample size" is small (a "subset" of available studies, small k); abstract-level '
            'extraction only (no full text, pattern-based screening, no RoB2/GRADE/PRISMA)')


def _phase_write(o: Orchestrator) -> None:
    """7 free-worker section drafts -> codex composition into paper_draft_v0.qmd."""
    c = o.dossier.data["contract"]
    metrics = o.dossier.data.get("pack_ext", {}).get("metrics_block", "")
    fig_hint = _fig_hint(o, c)
    kind = _paper_kind(c)
    (o.run_dir / "sections").mkdir(exist_ok=True)
    # free workers draft each section (the bulk; offloaded to the free worker tier)
    packets = [WorkerPacket(
        task_id=f"draft-{s.replace(' ', '_')}", role=f"section:{s}", worker_class="drafter",
        task_goal=_hdr(c) + f"""
You draft ONLY the "{s}" section of {kind}. Read:
{_skill('paper-draft', 'academic-writing')}
Inputs: phase3_positioning.md (gap), phase4_structure.md (outline), claim_evidence_map.md (allowed
claims), references.bib. Write `sections/{s.replace(' ', '_')}.md` — prose for the {s} section only,
academic English, citing references.bib by @key. Reference figures ONLY as {fig_hint}
(no image embeds, no {{#fig-}} labels). Use ONLY these admissible numbers, verbatim:

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
Assemble these section drafts into a complete Quarto `paper_draft_v0.qmd` (>=4500 words) for {kind}:
{chr(10).join('- ' + d for d in drafted)}
Plus an Abstract you write. Frontmatter: title, author "Cooperation.TW / Paper Lab", bibliography
references.bib, colorlinks/link-citations/citecolor blue. Cite >=20 references. Reference figures ONLY by
{fig_hint} in prose (NO image embeds, NO {{#fig-}} labels — the pipeline injects
each figure once). Fix any number that does not match real_experiments/real_results.json. State in
Limitations that {_limitations_hint(c)}. Only write paper_draft_v0.qmd. End with CHILD_OK."""
    _dispatch_brain(o, "phase8_compose", compose, ["paper_draft_v0.qmd"], timeout=1200)


def _render(run_dir: Path, contract: dict[str, Any]) -> bool:
    # canonical render lives in format_repair so the pipeline and the format-repair loop
    # render identically (re-inject tables + figures with the FIXED placement, then compile).
    return format_repair.render(run_dir, contract)


def _phase_render_gates(o: Orchestrator) -> None:
    _render(o.run_dir, o.dossier.data["contract"])
    # build the gate dossier view + run C/D/F (B already enforced after claim-evidence)
    draft = (o.run_dir / "paper_draft_v0.qmd")
    gd = {
        "draft_text": draft.read_text(encoding="utf-8") if draft.exists() else "",
        "qmd_text": draft.read_text(encoding="utf-8") if draft.exists() else "",
        "evidence": o.dossier.data.get("evidence", {}),
        "real_results": _read(o.run_dir / "real_experiments" / "real_results.json"),
        "claim_evidence": _claim_matrix_rows(o.run_dir),    # Gate B (meta) reads the matrix
        "render_ok": draft.exists(),
        "viability": o.dossier.data.get("viability", {}),     # Gate E (meta) reads this
    }
    report = run_gates(PaperPack(), gd, only={"B", "C", "D", "E", "F"})
    o.dossier.data.setdefault("gates", {})["render"] = report.as_dict()
    # Gate E (research value, WARN): the a-side CONFIRMS VALUE (the b-side confirmed the
    # GAP). Surface it for the report page + the heal loop. A well-powered null is valuable.
    for _r in report.results:
        if _r.gate == "E":
            o.dossier.data["research_value"] = (_r.evidence or {}).get("research_value")
    # Gate B (claim<=evidence, BLOCK) HARD-enforced for the dataset lane: the negation-aware
    # qualitative check (no non-disclaimed causal/universal/overreach; numbers gated by
    # number_trace). Verified clean on an honest paper (0 flags). Meta keeps RECORDED until
    # its matrix path's precision is verified on a fresh meta run (enforce-then-false-block
    # is worse than record).
    if _is_dataset_lane(o.dossier.data["contract"]):
        _b = next((r for r in report.results if r.gate == "B"), None)
        if _b is not None and not _b.passed:
            o.dossier.save()
            o.dossier.update_status(blocked=True, blockers=["claim_evidence_B"])
            raise OrchestratorBlocked("render_gates", reason="Gate B (claim exceeds evidence): "
                                      + (_b.details or "qualitative overclaim"))
    # Dataset lane: every manuscript number must trace to the analysis output (no
    # hallucinated statistics). The meta lane has its own claim-evidence path; this adds
    # the number-trace gate for agent-run dataset analyses.
    if _is_dataset_lane(o.dossier.data["contract"]) and draft.exists():
        import dataset_lane
        rr = gd["real_results"] or {}
        yrs = {str(y) for y in range(1990, 2031)}        # bare years are not analysis numbers
        traced = dataset_lane.gates.number_trace(gd["qmd_text"], rr, whitelist=yrs)
        o.dossier.data["gates"]["number_trace"] = [p["id"] for p in traced]
        # HARD BLOCK on a real hallucination pattern. number_trace is now parsing-precise
        # (ranges/sci-notation/frontmatter no longer misfire); a lone stray token can still
        # be a methods-rule constant ("30 observations"), so block only on >=3 untraced —
        # a genuine fabrication comes in bunches, never as one rule number.
        n_untraced = sum(len(p.get("numbers") or []) for p in traced)
        if n_untraced >= 3:
            o.dossier.save()
            o.dossier.update_status(blocked=True, blockers=["number_trace"])
            raise OrchestratorBlocked("render_gates", reason=(
                f"{n_untraced} manuscript numbers do not trace to real_results "
                "(hallucinated statistics) — claim must not exceed evidence"))
    o.dossier.save()


def _read(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _doi_real_rate(run_dir: Path) -> float | None:
    """The CrossRef real-existence rate from the DOI audit — so Gate A can evaluate its
    DOI-realness half (refs>=35 AND doi_real_rate>=0.80), not just the count."""
    audit = _read(run_dir / "doi_audit.json")
    r = audit.get("real_rate") if isinstance(audit, dict) else None
    return float(r) if isinstance(r, (int, float)) else None


def _claim_matrix_rows(run_dir: Path) -> list[str]:
    """The claim-evidence matrix table rows for Gate B's meta path (the dataset path uses
    its own negation-aware qualitative check and ignores the matrix)."""
    p = run_dir / "claim_evidence_map.md"
    if not p.is_file():
        return []
    return [ln for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines() if "|" in ln]


def _phase_review_heal(o: Orchestrator) -> None:
    """Phase 9: codex 7-dim review + deterministic floor; free-worker fix-agents."""
    c = o.dossier.data["contract"]

    def review_fn(_data: dict[str, Any], rnd: int) -> ReviewOutcome:
        # The brain DIAGNOSES *and PRESCRIBES* in ONE call: for every problem it emits
        # a concrete, executable edit (verbatim locator + exact replacement). The
        # free worker that applies them is NOT smart — it only finds the locator and
        # writes the replacement. The intelligence is all here, in codex.
        # JUDGMENT checks the RENDERED PDF too, not just the source: a broken crossref is
        # invisible in the qmd (ref + label both present) — only the compiled PDF shows it.
        rdefs = format_repair.broken_crossrefs(o.run_dir)
        rdef_note = ("\nThe COMPILED PDF has UNRESOLVED figure cross-references "
                     "(`?@fig-`/`?@tbl-`) — flag this; the figures must reference-resolve."
                     ) if rdefs else ""
        prompt = _hdr(c) + f"""
You are the REVIEW brain (independent — you did NOT write this). Read:
{_skill('paper-draft', 'paper-review-skill', 'elite-reviewer-audit', 'paper-logic-audit', 'figure-table-checker')}
Review paper_draft_v0.qmd vs real_experiments/real_results.json + claim_evidence_map.md as a tough
Q1 reviewer on the 7 dimensions. Also VERIFY the deliverable renders: every @fig-/@tbl- reference must
resolve (no `?@` in the PDF) and figures/tables must be present.{rdef_note}
Write `quality_review_round{rnd}.json` with this EXACT shape:
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
EXPLICITLY contains these honest caveats, all genuinely true here, using these exact phrasings:
{_limitations_caveats(c)}. Always include at least one P1 edit whose replacement is a 3-5 sentence
Limitations paragraph containing those phrases (locator = the existing Limitations heading or first
sentence). Do NOT edit the paper yourself. End with CHILD_OK."""
        _dispatch_brain(o, f"review_round{rnd}", prompt, [f"quality_review_round{rnd}.json"])
        o.dossier.pack_ext_set("render_defects", [d.get("id") for d in rdefs])
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

    # the self-heal loop dispatches free-worker fix-agents on each failing round.
    # GRACEFUL DEGRADATION: review is the final POLISH — a rendered draft + a deterministic
    # floor already exist. If review cannot complete (e.g. codex usage limit even after the
    # big-pickle fallback), DELIVER the draft with a recorded note instead of crashing the
    # whole run. Never stuck with no output.
    loop = _PaperSelfHeal(o, review_fn, target_score=SCORE_TARGET, max_rounds=3)
    result = None
    try:
        result = loop.run()
    except OrchestratorBlocked as exc:
        o.dossier.data.setdefault("degraded", []).append(
            {"phase": "review_heal", "reason": f"review incomplete ({exc}); delivered the rendered draft"})
    # ACT on the review outcome — never let the phase complete silently with the loop's
    # blocked status ignored. A deterministic INTEGRITY hard-gate failure (analysis not
    # completed / simulated / a P0 consistency error) is a TERMINAL content block: a
    # fabricated or incomplete analysis must NOT deliver, even degraded. (A soft score
    # below target is NOT a hard block — the loop did its best; we record the verdict.)
    hg = floor_score.hard_gates(o.run_dir)
    o.dossier.pack_ext_set("review_verdict", {
        "status": getattr(result, "status", "degraded"),
        "rounds": getattr(result, "rounds", None),
        "hard_gates_pass": hg.get("all_pass")})
    if not hg.get("all_pass", True):
        o.dossier.save()
        o.dossier.update_status(blocked=True, blockers=["floor_hard_gates"])
        raise OrchestratorBlocked("review_heal",
                                  reason=f"integrity hard-gates failed (not deliverable): {hg}")
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


def _phase_format_repair(o: Orchestrator) -> None:
    """Phase 9b: render the PDF and VERIFY the figure/table cross-references resolve
    (the one render fact the source-only review can't see), re-rendering at most ONCE.
    The real fix is by-construction (tables.inject_figures places floats in the body);
    this is the cheap last check, deliberately NOT a stack of mechanical auto-repairs."""
    result = format_repair.verify_and_repair(o.run_dir, o.dossier.data["contract"])
    o.dossier.data.setdefault("gates", {})["format_repair"] = result
    o.dossier.save()


def build_paper_phases() -> list[Phase]:
    return [
        Phase("data", _phase_data, gates=frozenset({"A"}),
              checkpoint_artifacts=["real_experiments/real_results.json", "references.bib"]),
        Phase("gap", _phase_gap, checkpoint_artifacts=["phase3_positioning.md"]),
        Phase("structure", _phase_structure, checkpoint_artifacts=["phase4_structure.md"]),
        Phase("claim_evidence", _phase_claim_evidence, checkpoint_artifacts=["claim_evidence_map.md"]),
        Phase("write", _phase_write, checkpoint_artifacts=["paper_draft_v0.qmd"]),
        Phase("render_gates", _phase_render_gates, checkpoint_artifacts=["paper_draft_v0.pdf"]),
        Phase("review_heal", _phase_review_heal, checkpoint_artifacts=["paper_draft_v0.qmd"]),
        Phase("format_repair", _phase_format_repair, checkpoint_artifacts=["paper_draft_v0.pdf"]),
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
