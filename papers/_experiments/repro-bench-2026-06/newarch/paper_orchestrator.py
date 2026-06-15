#!/usr/bin/env python3
"""Architecture B orchestrator (meta-analysis lane) — see HERMES_NATIVE_ORCHESTRATOR_DESIGN.md.

Python owns the CONTROL PLANE (state machine, dossier, gates, 3-round self-heal). The strong
brain is the subscription **codex** CLI (gap / structure / claim-evidence / writing / review / fix);
the deterministic assets (meta-analysis lane, figures, tables, render, floor_score, audits) are
REUSED as tools. This is NOT the old assembly line: strong brain + full 28-skill bundle in context
+ dossier reasoning-handoff + matrix gates + self-heal, vs the old weak per-phase one-shots.

Run ON ac-2012 (codex + assets + skill bundle live there), inside the newarch dir so imports resolve.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import paper_driver as PD           # run_meta_analysis_lane, expand_references_from_analysis, meta_metrics_block, doi_gate
import meta_figures
import tables
import render_springer
import delivery_audit
import floor_score
import phase0_calibration

SKILLS = Path.home() / "paperbench" / "skills-bundle"
SCORE_TARGET = 80.0                  # /100 (floor_score is /10 -> x10)


def log(m: str) -> None:
    print(f"[orch] {m}", flush=True)


def read_json(p: Path, d: Any = None) -> Any:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return d


def write_json(p: Path, o: Any) -> None:
    Path(p).write_text(json.dumps(o, ensure_ascii=False, indent=2), encoding="utf-8")


# ── dossier: the reasoning-continuity checkpoint (not just artifacts) ─────────
def dossier_set(run_dir: Path, section: str, value: Any) -> dict[str, Any]:
    d = read_json(run_dir / "dossier.json", {}) or {}
    d[section] = value
    d.setdefault("_history", []).append({"set": section, "at": int(time.time())})
    write_json(run_dir / "dossier.json", d)
    return d


# ── the strong brain: subscription codex CLI, workspace-write, in run_dir ─────
def codex_brain(run_dir: Path, label: str, prompt: str, timeout: int = 900) -> bool:
    logd = run_dir / "_orch_logs"
    logd.mkdir(exist_ok=True)
    (logd / f"{label}.prompt.txt").write_text(prompt, encoding="utf-8")
    log(f"codex[{label}] running…")
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["codex", "exec", "--skip-git-repo-check", "--sandbox", "workspace-write", prompt],
            cwd=str(run_dir), stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        log(f"codex[{label}] TIMEOUT after {timeout}s")
        return False
    (logd / f"{label}.stdout.txt").write_text(proc.stdout + "\n--STDERR--\n" + proc.stderr, encoding="utf-8")
    log(f"codex[{label}] rc={proc.returncode} {round(time.time()-t0)}s")
    return proc.returncode == 0


def _skill(*names: str) -> str:
    return "\n".join(f"- {SKILLS}/{n}/SKILL.md" for n in names)


CONTRACT_HDR = (
    "Governing research contract (do NOT change the topic):\n"
    "- Topic: {topic}\n- Research question: {rq}\n- Contribution: {contrib}\n"
    "- Target journal tier: {tier}\nRules: academic English; no emoji; no invented numbers; "
    "every numeric claim must trace to real_experiments/real_results.json; ground every citation in "
    "references.bib (never fabricate DOIs/authors).\n"
)


def _hdr(c: dict[str, Any]) -> str:
    return CONTRACT_HDR.format(topic=c.get("topic"), rq=c.get("research_question"),
                               contrib=c.get("contribution"), tier=c.get("target_journal"))


# ── phases ───────────────────────────────────────────────────────────────────
def phase_data(run_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Deterministic lane: pool real effects + build verified refs + draw figures."""
    log("phase-data: meta-analysis lane (deterministic)")
    result = PD.run_meta_analysis_lane(run_dir, contract)            # writes real_results.json + figures
    kept = PD.expand_references_from_analysis(run_dir, contract, result)
    prisma = (result.get("meta") or {}).get("prisma") or {}
    dossier_set(run_dir, "evidence", {
        "studies_with_effects": prisma.get("studies_with_effects"),
        "pooled": (result.get("meta") or {}).get("pooled"),
        "refs_kept": kept,
        "real_results": "real_experiments/real_results.json",
    })
    log(f"phase-data: studies={prisma.get('studies_with_effects')} refs={kept}")
    return result


def phase_gap(run_dir: Path, contract: dict[str, Any]) -> bool:
    prompt = _hdr(contract) + f"""
You are the RESEARCH-POSITIONING brain. Read these skills for the method:
{_skill('paper-draft','literature-synthesis','innovation-positioning')}
Phase 3 of paper-draft. Inputs in THIS directory: dossier.json, references.bib,
real_experiments/real_results.json (the pooled abstract-level meta-analysis).
Write `phase3_positioning.md` containing:
1. A literature landscape (3-4 short paragraphs grouping the real references by what they did).
2. A real Gap Matrix table: | Gap | Description | Existing Work | Our Approach | with >=3 gaps; the
   "Existing Work" cell MUST cite actual entries from references.bib (real author/year), never invented.
3. A Differentiation Statement ("Unlike prior work that X, our study Y by Z").
4. A Contribution Echo: 3 contribution points, each tied to a gap.
Only write that one file. Be concrete and adversarial about the gap — no generic "no prior work combines X and Y".
"""
    ok = codex_brain(run_dir, "phase3_gap", prompt)
    if (run_dir / "phase3_positioning.md").exists():
        dossier_set(run_dir, "claims_positioning", "phase3_positioning.md")
    return ok and (run_dir / "phase3_positioning.md").exists()


def phase_structure(run_dir: Path, contract: dict[str, Any]) -> bool:
    prompt = _hdr(contract) + f"""
You are the PAPER-STRUCTURE brain. Read: {_skill('paper-draft','figure-design','qmd-writer')}
Phase 4. Inputs: dossier.json, phase3_positioning.md, references.bib, real_experiments/real_results.json.
Write `phase4_structure.md`: section outline (Abstract, Introduction, Related Work, Methods, Results,
Discussion, Limitations, Conclusion), the key claim of each section, the planned figures/tables (the
deterministic pipeline already produced a forest plot, PRISMA flow, method-overview + pooled/sensitivity
tables — reference those by @fig-forest/@fig-prisma/@fig-method/@tbl-*), and expected word counts
(target 4500-6000 words total). Only write that one file.
"""
    ok = codex_brain(run_dir, "phase4_structure", prompt)
    return ok and (run_dir / "phase4_structure.md").exists()


def gate_b_claim_evidence(run_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Codex builds the claim-evidence matrix; a deterministic check enforces it."""
    prompt = _hdr(contract) + f"""
You are the CLAIM-EVIDENCE (Gate B) brain. Read: {_skill('paper-draft','paper-review-skill')}
Inputs: real_experiments/real_results.json, phase3_positioning.md, phase4_structure.md.
Write `claim_evidence_map.md`: a table | Claim | Evidence (which real_results field/table/figure) |
Exact-Match? | N-Support | Attribution-verb | for EVERY quantitative claim the paper will make.
Rules (any violation = fix it BEFORE writing): numbers must equal real_results exactly; N<3 forces a
"sample too small" caveat; attribution verb tier by N+effect (N>=10 & p<0.01 -> dominates/causes;
N in [3,10] -> correlates/associated; N<3 -> suggests/consistent-with, strong causal verbs BANNED).
Only write that one file.
"""
    ok = codex_brain(run_dir, "gate_b", prompt)
    cem = run_dir / "claim_evidence_map.md"
    verdict = {"built": ok and cem.exists(), "rows": 0}
    if cem.exists():
        verdict["rows"] = cem.read_text(encoding="utf-8").count("|") // 5
    write_json(run_dir / "gate_b.json", verdict)
    return verdict


def phase_write(run_dir: Path, contract: dict[str, Any], result: dict[str, Any]) -> bool:
    metrics = PD.meta_metrics_block(result)
    prompt = _hdr(contract) + f"""
You are the PAPER-WRITING brain (composition over 7 sections). Read:
{_skill('paper-draft','academic-writing','qmd-writer','journal-templates')}
Inputs: phase3_positioning.md (gap), phase4_structure.md (outline), claim_evidence_map.md (allowed
claims), references.bib. Write the complete `paper_draft_v0.qmd` (Quarto), >=4500 words across
Abstract, Introduction, Related Work, Methods, Results, Discussion, Limitations, Conclusion.
Frontmatter: title, author "Cooperation.TW / Paper Lab", bibliography references.bib,
colorlinks/link-citations/citecolor blue. Cite >=20 references. Reference the pre-generated figures
ONLY by writing @fig-forest / @fig-prisma / @fig-method in prose (and @tbl-* for tables). Do NOT write
any image embed (no ![...](...)) and no {{#fig-...}} label anywhere — the pipeline injects each figure
exactly once. Writing an image embed or figure label is an error that causes duplicate figures.
Honesty: this is an abstract-level random-effects meta-analysis (no full text / no PRISMA SR); state
that in Limitations. Use ONLY these admissible numbers, verbatim:

{metrics}

Only write paper_draft_v0.qmd.
"""
    ok = codex_brain(run_dir, "phase8_write", prompt, timeout=1200)
    return ok and (run_dir / "paper_draft_v0.qmd").exists()


def render(run_dir: Path, contract: dict[str, Any]) -> bool:
    try:
        tables.inject(run_dir, contract)
        tables.inject_figures(run_dir)
    except Exception as e:  # noqa: BLE001
        log(f"table/figure inject warn: {e}")
    ok = render_springer.render(run_dir, contract)
    log(f"render: {'PDF ok' if ok else 'FAILED'}")
    return ok


def score(run_dir: Path) -> dict[str, Any]:
    fs = floor_score.floor_scores(run_dir)
    audit = delivery_audit.audit(run_dir)
    overall10 = fs.get("mean_6_floor") or 0
    out = {"floor_overall_10": overall10, "floor_overall_100": round(float(overall10) * 10, 1),
           "dimensions": fs.get("scores_7dim"), "hard_gates": fs.get("hard_gates"),
           "delivery_audit": audit.get("verdict")}
    write_json(run_dir / "orch_score.json", out)
    return out


def review_and_heal(run_dir: Path, contract: dict[str, Any], rounds: int) -> dict[str, Any]:
    """Phase 9: deterministic floor + codex 7-dim review; self-heal up to `rounds`."""
    history = []
    for r in range(1, rounds + 1):
        sc = score(run_dir)
        log(f"round {r}: floor={sc['floor_overall_100']}/100 audit={sc['delivery_audit']}")
        prompt = _hdr(contract) + f"""
You are the REVIEW brain (independent — you did NOT write this). Read:
{_skill('paper-draft','paper-review-skill','elite-reviewer-audit','paper-logic-audit')}
Review paper_draft_v0.qmd against real_experiments/real_results.json + claim_evidence_map.md.
Write `quality_review_round{r}.json`: {{"score_100": <int>, "p0": [..], "p1": [..],
"fixes": [<concrete edit instructions>]}}. Score on the 7 dimensions (gap clarity, methodology,
results significance, writing, citations, contribution, figures). Be a tough Q1 reviewer.
Then, if score_100 < {int(SCORE_TARGET)} OR any p0: APPLY your own fixes directly by editing
paper_draft_v0.qmd (and only it) to resolve every p0 and raise the score — do not invent numbers,
keep claims <= evidence. If already >= {int(SCORE_TARGET)} and no p0, change nothing.
"""
        codex_brain(run_dir, f"review_round{r}", prompt, timeout=1200)
        rev = read_json(run_dir / f"quality_review_round{r}.json", {}) or {}
        render(run_dir, contract)                       # re-render after any edits
        sc2 = score(run_dir)
        history.append({"round": r, "review_score": rev.get("score_100"),
                        "floor_100": sc2["floor_overall_100"], "p0": len(rev.get("p0") or [])})
        log(f"round {r} done: review={rev.get('score_100')} floor={sc2['floor_overall_100']} p0={len(rev.get('p0') or [])}")
        if (rev.get("score_100") or 0) >= SCORE_TARGET and not (rev.get("p0") or []):
            log(f"round {r}: PASS (>= {SCORE_TARGET}, no P0)")
            break
    write_json(run_dir / "selfheal_history.json", history)
    return {"history": history, "final": score(run_dir)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--rounds", type=int, default=3)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    contract = read_json(run_dir / "research_contract.json") or read_json(run_dir / "contract.json")
    if not contract:
        log("no contract"); return 2
    dossier_set(run_dir, "run", {"lane": "meta-analysis", "rounds": args.rounds})
    dossier_set(run_dir, "contract", {k: contract.get(k) for k in
                ("topic", "research_question", "contribution", "target_journal", "synthesis")})

    # Phase 0 viability (deterministic gate)
    cal = phase0_calibration.run_phase0(run_dir, contract, PD._literature_query(contract))
    if not cal.get("viable"):
        log(f"phase0 NOT VIABLE: {cal.get('reason')}"); return 3
    contract = cal.get("contract") or contract

    result = phase_data(run_dir, contract)              # deterministic data lane
    if not phase_gap(run_dir, contract):     log("gap phase failed"); return 4
    if not phase_structure(run_dir, contract): log("structure phase failed"); return 4
    gate_b_claim_evidence(run_dir, contract)            # matrix gate (brain builds + det. check)
    meta_figures.generate(run_dir)                      # ensure figures present
    if not phase_write(run_dir, contract, result): log("write phase failed"); return 4
    render(run_dir, contract)
    outcome = review_and_heal(run_dir, contract, args.rounds)

    fs = outcome["final"]
    log("=" * 60)
    log(f"FINAL: floor={fs['floor_overall_100']}/100  audit={fs['delivery_audit']}")
    log(f"self-heal rounds: {[h['round'] for h in outcome['history']]}")
    write_json(run_dir / "orch_result.json", outcome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
