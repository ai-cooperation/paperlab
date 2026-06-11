#!/usr/bin/env python3
"""Contract-driven, phase-bounded Hermes driver for the real paper-draft pipeline.

Route A replacement for the mock ``run_newarch.py``. This drives the real
paper-draft 11-phase skill (MVP subset: phases 1-4, 7-9) plus a real 3-layer
review, through the Hermes agentic CLI, one phase per fresh subprocess.

Why per-phase processes (do NOT regress): a single Hermes mega-session crosses
the context-compression threshold near the end of a paper run; Hermes then
rotates its session id and the continuation row loses cwd/messages, so the run
hangs. Keeping each phase in a fresh process with files-on-disk as the only
checkpoint boundary is the fix (origin: run_hermes_phasefix.py, 2026-06-05).

Lanes:
- ``cpu-real``: run the real HUPD CPU experiment and write real values into the
  results phase (no ``^S^`` simulated markers).
- ``mvp``: skip experiments, use statistically self-consistent simulated values
  marked ``^S^`` (faster, for non-experimental venues).

The driver emits the artifact contract that ``job_runner.extract_output()``
consumes: ``final_content_review_deterministic.json``, ``gate_report.json``,
``newarch_trace.json``, ``real_experiments/real_results.json``, ``metadata.json``,
``paper_draft_v0.pdf``. See ROUTE_A_PLAN.md section 3.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import hashlib
import platform

import capabilities
import compile_review
import consistency_gate
import doi_audit
import render_springer
import revision_tasks
import tables

SCRIPT_DIR = Path(__file__).resolve().parent
HOME = Path.home()
HERMES = Path(os.environ.get("PAPER_HERMES_BIN", HOME / ".hermes/hermes-agent/venv/bin/hermes"))
HERMES_INPUT = Path(os.environ.get("PAPER_HERMES_INPUT", HOME / "paperbench/hermes-input"))

# Real-existence rate (CrossRef, non-arXiv determinable DOIs) below which the
# job fails closed. Neutralises the proven free-model habit of fabricating DOIs.
DOI_REAL_RATE_FLOOR = float(os.environ.get("PAPER_DOI_FLOOR", "0.80"))

PAPER_PHASES = ("phase1", "phase2", "phase3", "phase4", "phase7", "phase8", "phase9")

EXPECTED: dict[str, list[str]] = {
    "phase1": ["phase1_concept.md"],
    "phase2": ["references.bib", "metadata.json", "doi_verification_report.md"],
    "phase3": ["phase3_positioning.md"],
    "phase4": ["phase4_structure.md"],
    "phase7": ["figures", "tables"],
    "phase8": ["paper_draft_v0.qmd"],
    "phase9": [
        "claim_evidence_map.md",
        "figure_audit.md",
        "coherence_audit.md",
        "gate_d_readability.md",
        "quality_review_log.md",
        "progress.md",
    ],
    "review_mvp": ["mvp_check_report.md"],
    "review_7dim": ["paper_review_report.md"],
    "review_elite": ["elite_audit_report.md"],
    "review_tasks": ["review_tasks_fallback.json"],
    "revision": ["paper_draft_v0.qmd"],
}


def expected_key(key: str) -> str:
    """Map a per-round phase key (e.g. 'review_mvp_r1', 'revision_r2') to its base
    EXPECTED entry, so the revision loop can reuse run_hermes/verify."""
    base = re.sub(r"_r\d+$", "", key)
    return "revision" if base.startswith("revision") else base


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat()


def load_contract(run_dir: Path) -> dict[str, Any]:
    for name in ("research_contract.json", "contract.json"):
        path = run_dir / name
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    raise FileNotFoundError(f"no research_contract.json/contract.json in {run_dir}")


def provider_for(model: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    m = model.lower()
    if m.startswith("gemini"):
        return "gemini"
    if m.startswith("gpt") or m in {"codex", "openai-codex"}:
        return "openai-codex"
    # big-pickle / deepseek / local => config.yaml custom @127.0.0.1:8898
    return "custom"


def base_requirements(contract: dict[str, Any], lane: str) -> str:
    if lane == "cpu-real":
        data_rule = (
            "- This is a real-data run. Phase 7 must read real_experiments/real_results.json "
            "and use ONLY those real values. Do NOT invent numbers and do NOT use ^S^ markers."
        )
    else:
        data_rule = (
            "- MVP mode. Skip real experiments and use statistically self-consistent simulated "
            "values marked with ^S^ based on the contract's expected-results framing."
        )
    skills = "\n".join(
        f"- {HERMES_INPUT / s}"
        for s in (
            "paper-draft.SKILL.md",
            "simulated-data.SKILL.md",
            "doi-verifier.SKILL.md",
        )
    )
    lang = str(contract.get("output_language") or "en").lower()
    lang_rule = (
        "- Write ALL paper prose in Traditional Chinese (繁體中文). Keep citation keys, "
        "table/figure ids, code, and metric names in English."
        if lang == "zh" else
        "- Write ALL paper prose in academic English."
    )
    return f"""Read only the skill/context files needed for this bounded phase:
{skills}

Research contract (governing — do not change topic):
- Topic: {contract.get('topic')}
- Research question: {contract.get('research_question')}
- Contribution: {contract.get('contribution')}
- Target journal: {contract.get('target_journal')}
- Data source: {(contract.get('data_source') or {}).get('name')}

Rules:
- Output directory is the current working directory. Write ALL outputs only here.
{data_rule}
{lang_rule}
- Use existing files in this directory as checkpoints. Do not redo completed phases
  unless required to repair consistency.
- Ask no questions. No emoji.
"""


def analysis_metrics_block(result: dict[str, Any]) -> str:
    """Scientometric-lane counterpart of real_metrics_block: render the OpenAlex
    analysis as the ONLY admissible numbers (verbatim transcription, no invention)."""
    a = result.get("analysis") or {}
    cit = a.get("citations") or {}
    lines = [
        "REAL SCIENTOMETRIC DATA (OpenAlex) — these are the ONLY admissible numbers for",
        "tables/figures/prose. Transcribe exact values; do NOT invent or extrapolate.",
        "",
        f"Topic: {a.get('topic')} | corpus total: {a.get('openalex_total_count')} works | "
        f"analysed sample: {a.get('sample_size')} | year range: {a.get('year_range')}",
        f"Citations over sample: total={cit.get('total')} mean={cit.get('mean')} "
        f"median={cit.get('median')} max={cit.get('max')}",
        "",
        "Publications per year (verbatim): " + json.dumps(a.get("publications_per_year") or {}),
        "Top venues (verbatim): " + json.dumps(a.get("top_venues") or [])[:700],
        "Top authors (verbatim): " + json.dumps(a.get("top_authors") or [])[:700],
        "Top concepts (verbatim): " + json.dumps(a.get("top_concepts") or [])[:700],
        "Most-cited works (verbatim): " + json.dumps(a.get("most_cited") or [])[:900],
    ]
    return "\n".join(lines)


def meta_metrics_block(result: dict[str, Any]) -> str:
    """Meta-analysis lane: pooled estimates + per-study effects as the ONLY
    admissible numbers (each effect carries its verbatim evidence sentence)."""
    m = result.get("meta") or {}
    lines = [
        "REAL META-ANALYSIS DATA (OpenAlex abstracts, mechanical extraction) — the ONLY",
        "admissible numbers. Transcribe exact values; do NOT invent or re-pool anything.",
        "",
        "PRISMA-style counts (verbatim): " + json.dumps(m.get("prisma") or {}),
        "Pooled estimates per measure (verbatim): " + json.dumps(m.get("pooled") or {}),
        "",
        "Per-study extracted effects (verbatim; cite by title/year/doi):",
    ]
    for e in (m.get("effects") or [])[:25]:
        ci = (f" [{e.get('ci_low')}, {e.get('ci_high')}]"
              if e.get("ci_low") is not None else "")
        lines.append(f"- {e.get('measure')} {e.get('effect')}{ci} | n={e.get('n')} | "
                     f"{e.get('title')} ({e.get('year')}) doi:{e.get('doi')}")
    lines += [
        "",
        "ANALYSES PERFORMED — write Methods/Results to match EXACTLY this and nothing more:",
        "DerSimonian-Laird random-effects pooling per effect measure (with I^2/tau^2) on the",
        "extracted abstract-level effects. NO subgroup analysis, NO meta-regression, NO",
        "funnel plot / Egger test, and NO full-text PRISMA screening were performed — even if",
        "the proposal planned them. Do NOT claim them; list them under Limitations/Future Work.",
        "",
        "Methodological note (state in Limitations, verbatim meaning): " + str(m.get("note") or ""),
    ]
    return "\n".join(lines)


def metrics_block(result: dict[str, Any]) -> str:
    """Dispatch the verbatim-numbers block by result shape (ML benchmark vs
    scientometric analysis vs meta-analysis)."""
    if isinstance(result.get("meta"), dict):
        return meta_metrics_block(result)
    if isinstance(result.get("analysis"), dict):
        return analysis_metrics_block(result)
    return real_metrics_block(result)


def real_metrics_block(result: dict[str, Any]) -> str:
    """Render the real experiment metrics as an unambiguous table the writer must
    transcribe verbatim (prevents the model inventing plausible-but-fake numbers)."""
    rows = result.get("benchmark") if isinstance(result.get("benchmark"), list) else []
    lines = [
        "REAL EXPERIMENT RESULTS — these are the ONLY admissible numbers for tables/figures.",
        "Transcribe these exact values; do NOT invent, round away, or simulate any cell.",
        "",
        "| task | feature | model | holdout_acc | holdout_f1_macro | cv_f1_macro_mean | cv_f1_macro_std | f1_macro_ci95 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if not isinstance(r, dict):
            continue
        ho = r.get("holdout") or {}
        cv = (r.get("cv") or {}).get("f1_macro") or {}
        ci = (r.get("bootstrap_ci_95") or {}).get("f1_macro") or [None, None]
        def f(v: Any) -> str:
            return f"{float(v):.4f}" if isinstance(v, (int, float)) else "NA"
        ci_txt = f"[{f(ci[0])}, {f(ci[1])}]" if len(ci) == 2 else "NA"
        lines.append(
            f"| {r.get('task')} | {r.get('feature')} | {r.get('model')} | {f(ho.get('accuracy'))} | "
            f"{f(ho.get('f1_macro'))} | {f(cv.get('mean'))} | {f(cv.get('std'))} | {ci_txt} |"
        )
    tests = result.get("statistical_tests")
    if tests:
        lines += ["", "Statistical tests (use verbatim): " + json.dumps(tests)[:800]]
    sci = result.get("scientometrics")
    if sci:
        lines += ["Scientometrics (use verbatim): " + json.dumps(sci)[:800]]
    return "\n".join(lines)


def paper_prompt(phase: str, contract: dict[str, Any], lane: str, real_summary: str | None = None) -> str:
    base = base_requirements(contract, lane)
    bodies = {
        "phase1": """
Bounded task: complete Phase 1 (Concept) only.
Required output: phase1_concept.md derived from the governing contract above (keep the locked topic).
Append one line to progress.md only if phase1_concept.md exists. Stop after Phase 1.
""",
        "phase2": """
Bounded task: complete Phase 2 (Literature + DOI verification) only.
Inputs: phase1_concept.md.
Required outputs: references.bib, metadata.json, doi_verification_report.md.
Hard requirements: at least 35 BibTeX entries; every entry has a real DOI and an abstract field;
verify DOI existence against CrossRef before claiming success. If Semantic Scholar/OpenAlex is
unavailable, record unavailable rather than inventing. The independent scorer will re-check CrossRef.
Append one line to progress.md only after the files exist. Stop after Phase 2.
""",
        "phase3": """
Bounded task: complete Phase 3 (Positioning) only.
Inputs: phase1_concept.md, references.bib, metadata.json, doi_verification_report.md.
Required output: phase3_positioning.md with research gap, contribution positioning, novelty argument,
and citation-grounded comparison.
Append one line to progress.md only if the artifact exists. Stop after Phase 3.
""",
        "phase4": """
Bounded task: complete Phase 4 (Structure) only.
Inputs: phase1_concept.md, phase3_positioning.md, references.bib.
Required output: phase4_structure.md with section outline, key claims, planned figures/tables
(at least 3 figures and 2 tables), expected word counts, and evidence needs.
Append one line to progress.md only if the artifact exists. Stop after Phase 4.
""",
        "phase7": """
Bounded task: complete Phase 7 (Results, figures, tables) only.
Inputs: phase1_concept.md, phase4_structure.md. For cpu-real lane also read
real_experiments/real_results.json and use its real metrics verbatim. Follow the figure standards in
figure-design.SKILL.md (same skills directory as the skills listed above).
Required outputs: figures/ with at least 3 figures, each with both .svg and .png; tables/ with at
least 2 non-empty markdown tables; at least 5 figure+table artifacts total; no empty table cells.
Do NOT create or edit paper_draft_v0.qmd in this phase (that is Phase 8) — only write figures/ and
tables/. Never write line-number prefixes (like "12|") into any file.
FIGURE CORRECTNESS (critical, P0 if violated): every number, axis value, label, and annotation drawn
INSIDE a figure must come from real_experiments/real_results.json — the bootstrap resample count, fold
count, class count, model names, and metric values. Do NOT round to a "nice" number or invent values
(a figure that says "1,000 resamples" when the run used 300, or "9 classes" when it is 7, is a P0
error). Figure in-image text, captions, tables, and prose must all agree.
Figure quality (figure-design.SKILL.md): axis labels >=14pt, ticks >=13pt, >=300 DPI, no overlapping
labels, and do NOT use matplotlib fig.text() for captions (the QMD supplies them).
In table headers and cells use Unicode or ASCII symbols (Mean ± SD, alpha=0.05), never raw LaTeX
like $\\pm$ or $\\alpha$ — the renderer shows raw LaTeX literally.
Append one line to progress.md only after artifacts exist. Stop after Phase 7.
""",
        "phase8": """
Bounded task: complete Phase 8 (full QMD draft) only.
Inputs: phase1_concept.md, references.bib, metadata.json, phase3_positioning.md, phase4_structure.md,
figures/, tables/.
Required output: paper_draft_v0.qmd with fully detailed academic prose (>3000 words total across
Abstract, Introduction, Related Work, Methodology, Results, Discussion, Conclusion). No truncation.
Hard requirements: frontmatter includes colorlinks: true, link-citations: true, citecolor: blue;
author Cooperation.TW / Paper Lab / aicooperation.tw@gmail.com; at least 35 distinct in-text
citations; every bib entry cited; all figures cited via @fig-xx and tables via @tbl-xx.
{tables_directive}
If the run is cpu-real and the hardware is CPU-only, state in Limitations that neural transformer
(BERT) comparisons are excluded for lack of GPU.
Append one line to progress.md only if paper_draft_v0.qmd exists. Stop after Phase 8. Do not render.
""",
        "phase9": """
Bounded task: complete Phase 9 (quality gates + render) only. Do not rewrite the main paper unless a
concrete gate failure requires it.
Inputs: paper_draft_v0.qmd, references.bib, figures/, tables/, phase files.
Required artifacts: claim_evidence_map.md, figure_audit.md, coherence_audit.md, gate_d_readability.md,
quality_review_log.md.
Do NOT render a PDF here — the pipeline renders the journal-formatted PDF deterministically after
this phase (render_qmd_reportlab.py). Just produce the gate artifacts.
Write progress.md with one completed line per gate actually completed (only if its artifact exists).
Stop after Phase 9.
""",
    }
    body = bodies[phase]
    if phase == "phase8":
        # The machine-generated table set differs by lane (tables.py templates):
        # ML benchmark -> tbl-main + tbl-ablation; scientometric -> tbl-main + tbl-trend.
        ds_type = str((contract.get("data_source") or {}).get("type") or "").lower()
        if ds_type in ("meta-analysis", "meta_analysis"):
            tbl2, tbl2_desc = ("tbl-studies", "the per-study extracted-effects table")
        elif ds_type == "literature":
            tbl2, tbl2_desc = ("tbl-trend", "the publications-per-year trend table")
        else:
            tbl2, tbl2_desc = ("tbl-ablation", "the training-size ablation table")
        body = body.format(tables_directive=(
            "RESULTS TABLES ARE MACHINE-GENERATED — do NOT hand-write the numeric results tables. "
            "Where the main results table belongs, write exactly the single line "
            "`<!-- TABLE:tbl-main -->`; where " + tbl2_desc + " belongs, write exactly "
            f"`<!-- TABLE:{tbl2} -->`. Reference them in prose as @tbl-main and @{tbl2}. "
            "The pipeline fills these with verified numbers from real_results.json."
        ))
    if phase == "phase7":
        body += (
            "\n\nThe architecture/method/pipeline figure MUST be authored as TikZ, NOT matplotlib boxes: "
            "write a standalone .tex in figures/ matching the name referenced in the QMD (e.g. "
            "figures/fig1_pipeline_architecture.tex) by ADAPTING the template below — change node labels "
            "and band names to the real pipeline, keep the structure; use real_results values. The "
            "pipeline compiles the .tex to .png + .svg. Data plots (forest plots, distributions, bar "
            "charts) stay matplotlib with both .png and .svg.\n\nTikZ template (adapt, don't copy verbatim):\n"
            + TIKZ_TEMPLATE + "\n")
    if phase in {"phase7", "phase8"} and real_summary:
        body += "\n\n" + real_summary + "\n"
    return base + body


def review_prompt(kind: str, contract: dict[str, Any], lane: str) -> str:
    base_skill = {
        "review_mvp": HERMES_INPUT / "mvp-gatekeeper.SKILL.md",
        "review_7dim": HERMES_INPUT / "paper-review-skill.SKILL.md",
        "review_elite": HERMES_INPUT / "elite-reviewer-audit.SKILL.md",
        "review_tasks": HERMES_INPUT / "paper-review-skill.SKILL.md",
    }[kind]
    target_file = EXPECTED[kind][0]
    json_contract = (
        f"IMPORTANT: write the full report to the file {target_file} using your file-writing "
        "tool (printing it to the response is not sufficient). "
        f"End {target_file} with a fenced ```json block containing a SINGLE object. "
        "Emit raw values you actually derived from the prose — do NOT copy any example."
    )
    bodies = {
        "review_mvp": f"""Read {base_skill}. Audit paper_draft_v0.qmd and (if present)
real_experiments/real_results.json and research_contract.json using the mvp-gatekeeper skill.
Write mvp_check_report.md. {json_contract}
The json object must be: {{"p0_count": int, "p1_count": int,
"problems": [{{"id": str, "severity": "P0"|"P1"|"P2", "location": str, "type": str, "description": str}}]}}.
""",
        "review_7dim": f"""Read {base_skill}. Audit paper_draft_v0.qmd and references.bib using the
paper-review-skill (seven-dimension scoring). Read the actual prose; score what is on the page, not
what is promised. Write paper_review_report.md. {json_contract}
The json object must be: {{"scores_7dim": {{"novelty": float, "methodological_rigor": float,
"evidence_validity": float, "literature_grounding": float, "result_interpretation": float,
"limitation_honesty": float, "writing_coherence": float}}}} with each score on a 1.0-10.0 scale.
""",
        "review_elite": f"""Read {base_skill}. Audit paper_draft_v0.qmd using the elite-reviewer-audit
skill: evaluate the 12 dimensions, run the Gap four-question pressure test, and estimate the
desk-reject probability. Write elite_audit_report.md. {json_contract}
The json object must be: {{"desk_reject_probability": float}} between 0.0 and 1.0.
""",
        "review_tasks": f"""You already wrote mvp_check_report.md and paper_review_report.md.
Convert their findings into CONCRETE revision tasks against paper_draft_v0.qmd.
Write ONLY the file review_tasks_fallback.json (valid JSON, no prose, no markdown fences):
{{"tasks": [{{"id": str, "severity": "P0"|"P1", "type": "value_swap"|"block_rewrite",
"target_section": str, "target_content": str, "replacement_content": str,
"description": str}}]}}
HARD RULES — tasks violating them are mechanically discarded:
- target_content MUST be an EXACT verbatim quote copied from paper_draft_v0.qmd
  (open the file and copy the characters; do not paraphrase or re-type from memory).
- Do NOT touch anything between <!-- GENERATED:... --> markers, the YAML frontmatter,
  or citation keys.
- value_swap only for small exact substitutions; block_rewrite for sentence/paragraph
  level fixes (replacement_content then holds INSTRUCTIONS for the rewrite).
- At most 10 tasks; only findings that materially improve review scores.
""",
    }
    return base_requirements(contract, lane).split("Rules:")[0] + bodies[kind]


FALLBACK_TASK_CAP = 10


def load_fallback_review_tasks(run_dir: Path) -> tuple[list[dict[str, Any]], int]:
    """Load big-pickle's review tasks and mechanically drop hallucinations: a task
    whose target_content is not a VERBATIM substring of the manuscript references
    text that does not exist — the known free-model reviewer failure mode. Returns
    (kept_tasks, dropped_count)."""
    path = run_dir / "review_tasks_fallback.json"
    qmd = run_dir / "paper_draft_v0.qmd"
    if not path.is_file() or not qmd.is_file():
        return [], 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("tasks", [])
    except (json.JSONDecodeError, AttributeError, OSError):
        return [], 0
    text = qmd.read_text(encoding="utf-8", errors="ignore")
    text_norm = " ".join(text.split())
    kept: list[dict[str, Any]] = []
    dropped = 0
    for t in raw if isinstance(raw, list) else []:
        if not isinstance(t, dict):
            dropped += 1
            continue
        target = str(t.get("target_content") or "")
        if (t.get("severity") not in {"P0", "P1"}
                or t.get("type") not in {"value_swap", "block_rewrite"}
                or len(target.strip()) < 8
                or "GENERATED:" in target):
            dropped += 1
            continue
        if target not in text:
            # Whitespace-collapsed match still PROVES the quoted text exists
            # (not a hallucination) — but an exact replace can't apply, so the
            # task is demoted to an instruction-driven rewrite.
            if " ".join(target.split()) in text_norm:
                t = {**t, "type": "block_rewrite"}
            else:
                dropped += 1                                # the anti-hallucination gate
                continue
        kept.append(t)
        if len(kept) >= FALLBACK_TASK_CAP:
            break
    return kept, dropped


def verify(run_dir: Path, key: str) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for rel in EXPECTED[expected_key(key)]:
        path = run_dir / rel
        if not path.exists():
            missing.append(rel)
        elif path.is_file() and path.stat().st_size == 0:
            missing.append(rel + " (empty)")
    return not missing, missing


def run_hermes(run_dir: Path, key: str, prompt: str, model: str, provider: str, timeout_s: int) -> int:
    log_dir = run_dir / "_phase_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{key}.prompt.txt").write_text(prompt, encoding="utf-8")
    cmd = [str(HERMES), "-m", model, "--provider", provider, "-z", prompt]
    start = now()
    with (log_dir / f"{key}.stdout.txt").open("w") as out, (log_dir / f"{key}.stderr.txt").open("w") as err:
        try:
            proc = subprocess.run(cmd, cwd=run_dir, stdout=out, stderr=err, timeout=timeout_s)
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            err.write(f"\nPHASE_TIMEOUT after {timeout_s}s: {exc}\n")
            code = 124
    # Review phases sometimes print the full report (with its json block) to stdout
    # instead of writing the expected file. Capture stdout as the report so scoring
    # can proceed rather than fail closed on a mechanical write miss.
    if expected_key(key).startswith("review_"):
        _ok, _missing = verify(run_dir, key)
        if _missing:
            target = run_dir / EXPECTED[expected_key(key)][0]
            stdout_text = (log_dir / f"{key}.stdout.txt").read_text(encoding="utf-8", errors="ignore")
            if "```" in stdout_text and stdout_text.strip():
                target.write_text(stdout_text, encoding="utf-8")
    ok, missing = verify(run_dir, key)
    with (run_dir / "_phasefix_status.tsv").open("a") as f:
        f.write(f"{key}\t{code}\t{int(ok)}\t{start}\t{now()}\t{','.join(missing)}\n")
    print(f"{key}: exit={code} verified={ok} missing={missing}", flush=True)
    return 0 if ok else (code or 1)


def run_real_experiment(run_dir: Path, limit: int, timeout_s: int) -> dict[str, Any]:
    out_dir = run_dir / "real_experiments"
    script = SCRIPT_DIR / "real_patent_experiment.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--out", str(out_dir), "--limit", str(limit)],
        cwd=SCRIPT_DIR, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s,
    )
    result_path = out_dir / "real_results.json"
    if not result_path.is_file():
        raise RuntimeError(f"real experiment produced no real_results.json; stderr={proc.stderr[-500:]}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if proc.returncode != 0 or result.get("status") != "completed":
        reason = result.get("reason") or proc.stderr[-500:] or proc.stdout[-500:]
        raise RuntimeError(f"real experiment failed closed: {reason}")
    return result


def _literature_query(contract: dict[str, Any]) -> str:
    topic = str(contract.get("topic") or "").strip()
    ds = contract.get("data_source") or {}
    query = str(ds.get("name") or "").strip()
    if query.lower() in {"", "literature-only", "literature", "meta-analysis", "meta_analysis"}:
        query = topic
    return query or topic


def run_scientometric_analysis(run_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Literature-lane real-data step: collect + analyse the topic's OpenAlex corpus
    (openalex_analysis.py). Fail-closed like run_real_experiment — a blocked
    collection must never silently degrade into invented numbers."""
    import openalex_analysis
    result = openalex_analysis.run(_literature_query(contract), run_dir)
    if result.get("status") != "completed":
        raise RuntimeError(f"scientometric collection failed closed: {result.get('reason')}")
    return result


def run_meta_analysis_lane(run_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Meta-analysis lane: extract + pool quantitative effects from real abstracts
    (meta_analysis.py). Fail-closed: too few extractable studies blocks the job
    with an actionable reason instead of fabricating an answer."""
    import meta_analysis
    result = meta_analysis.run(_literature_query(contract), run_dir)
    if result.get("status") != "completed":
        raise RuntimeError(f"meta-analysis failed closed: {result.get('reason')}")
    return result


def expand_references_from_analysis(run_dir: Path, contract: dict[str, Any],
                                    result: dict[str, Any]) -> int:
    """Literature-lane bibliography, by construction: a 4-seed grill list cannot
    carry a paper (a meta-analysis MUST cite every included study; reviewers
    expect 30-60 refs). Merge the contract's DOI list with the analysis's own
    real papers — included-study DOIs + the corpus's most-cited background — and
    rebuild references.bib through the same single-CrossRef verify+complete path
    (fabricated/404 entries still drop; everything kept is real and on-topic)."""
    candidates = list(contract_doi_candidates(contract))
    seen = {c["doi"].lower() for c in candidates}

    def _add(doi: Any, key: Any = None) -> None:
        d = str(doi or "").strip().replace("https://doi.org/", "")
        if d and d.lower() not in seen:
            seen.add(d.lower())
            candidates.append({"key": key, "doi": d})

    meta = result.get("meta") or {}
    for e in meta.get("effects") or []:        # included studies — must be citable
        _add(e.get("doi"))
    analysis = result.get("analysis") or {}
    for w in (meta.get("background_works") or analysis.get("background_works")
              or analysis.get("most_cited") or []):
        _add(w.get("doi"))
    audit = build_refs_from_doi_list(run_dir, candidates)
    return int(audit.get("kept") or 0)


TIKZ_TEMPLATE = r"""\documentclass[border=10pt]{standalone}
\usepackage{tikz}
\usepackage[scaled]{helvet}\renewcommand\familydefault{\sfdefault}
\usetikzlibrary{positioning,fit,backgrounds,arrows.meta}
\definecolor{cA}{HTML}{EEF3FB}\definecolor{cB}{HTML}{EAFAEF}\definecolor{cC}{HTML}{FDEEEE}
\begin{document}
\begin{tikzpicture}[font=\small,
  box/.style={rounded corners=2pt, draw=black!45, fill=white, align=center, minimum height=12mm, text width=37mm, inner sep=4pt, line width=0.6pt},
  arr/.style={-{Stealth[length=2.6mm]}, draw=black!55, line width=1pt},
  bandlbl/.style={font=\footnotesize\bfseries, text=black!65}]
% --- ROW 1 nodes (left to right), then ROW 2, ROW 3. Edit labels/content; keep structure. ---
\node[box,fill=blue!8] (a1) {\textbf{Stage}\\[2pt]{\scriptsize detail}};
\node[box,fill=orange!18,right=14mm of a1] (a2) {\textbf{Stage}\\[2pt]{\scriptsize detail}};
\node[box,fill=blue!8,right=14mm of a2] (a3) {\textbf{Stage}\\[2pt]{\scriptsize detail}};
\draw[arr](a1)--(a2);\draw[arr](a2)--(a3);
\node[box,fill=green!14,below=30mm of a1,xshift=18mm] (b1) {\textbf{Stage}\\[2pt]{\scriptsize detail}};
\node[box,fill=green!14,right=14mm of b1] (b2) {\textbf{Stage}\\[2pt]{\scriptsize detail}};
\draw[arr](b1)--(b2);\draw[arr](a3) to[out=-90,in=90] (b2);
\node[box,fill=red!12,below=30mm of b1,xshift=-9mm] (c1) {\textbf{Stage}\\[2pt]{\scriptsize detail}};
\node[box,fill=red!12,right=14mm of c1] (c2) {\textbf{Stage}\\[2pt]{\scriptsize detail}};
\node[box,fill=black!10,right=14mm of c2] (c3) {\textbf{Output}\\[2pt]{\scriptsize detail}};
\draw[arr](c1)--(c2);\draw[arr](c2)--(c3);\draw[arr](b2) to[out=-90,in=90] (c1);
% Band labels sit at the TOP-LEFT corner (above the band box) so the curved
% inter-band arrows (which run down the right side) never cross the text.
\begin{scope}[on background layer]
\node[fill=cA,rounded corners=5pt,fit=(a1)(a2)(a3),inner sep=6mm,label={[bandlbl]above left:Band A}]{};
\node[fill=cB,rounded corners=5pt,fit=(b1)(b2),inner sep=6mm,label={[bandlbl]above left:Band B}]{};
\node[fill=cC,rounded corners=5pt,fit=(c1)(c2)(c3),inner sep=6mm,label={[bandlbl]above left:Band C}]{};
\end{scope}
\end{tikzpicture}
\end{document}"""


def compile_tikz_figures(run_dir: Path) -> list[str]:
    """Deterministically compile any figures/*.tex (TikZ) the model wrote into
    publication-quality .png + .svg. This is how architecture/method figures reach
    journal quality (vs matplotlib boxes); data plots stay matplotlib."""
    figdir = run_dir / "figures"
    if not figdir.is_dir() or not shutil.which("pdflatex"):
        return []
    done: list[str] = []
    for tex in sorted(figdir.glob("*.tex")):
        base = tex.stem
        # Deterministic normalization: the weak model ignores the template's label
        # placement and writes `above right`, which puts band labels under the
        # right-side inter-band arrows. Force `above left` (clear of the arrows)
        # regardless of what the model wrote.
        try:
            src = tex.read_text(encoding="utf-8", errors="ignore")
            fixed = src.replace("above right", "above left")
            if fixed != src:
                tex.write_text(fixed, encoding="utf-8")
        except Exception:
            pass
        try:
            subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
                           cwd=figdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            pdf = figdir / f"{base}.pdf"
            if pdf.is_file():
                subprocess.run(["pdftoppm", "-png", "-r", "300", "-singlefile", f"{base}.pdf", base],
                               cwd=figdir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                subprocess.run(["pdftocairo", "-svg", f"{base}.pdf", f"{base}.svg"],
                               cwd=figdir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                if (figdir / f"{base}.png").is_file():
                    done.append(base)
        except Exception:
            pass
        for ext in (".aux", ".log", ".pdf"):
            (figdir / f"{base}{ext}").unlink(missing_ok=True)
    return done


def render_pdf(run_dir: Path) -> bool:
    """Deterministic journal-format render. Primary path: a REAL Springer/elsarticle
    PDF via Quarto + xelatex (render_springer) — the same stack as the Paper Lab
    Scientometrics papers. Falls back to the reportlab renderer when Quarto is
    unavailable or the LaTeX compile fails, so the pipeline always yields a PDF."""
    qmd = run_dir / "paper_draft_v0.qmd"
    pdf = run_dir / "paper_draft_v0.pdf"
    if not qmd.is_file():
        return False
    log_dir = run_dir / "_phase_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    contract: dict[str, Any] = {}
    cpath = run_dir / "research_contract.json"
    if cpath.is_file():
        try:
            contract = json.loads(cpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            contract = {}
    if render_springer.render(run_dir, contract):
        return True
    # Fallback: reportlab plain render (no Quarto/LaTeX needed).
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "render_qmd_reportlab.py"), str(qmd), str(pdf)],
        cwd=run_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300,
    )
    ok = pdf.is_file() and pdf.stat().st_size > 1000
    if not ok:
        (log_dir / "render.stderr.txt").write_text((proc.stderr or proc.stdout or "")[-2000:], encoding="utf-8")
    return ok


def doi_gate(run_dir: Path) -> dict[str, Any]:
    """Independent CrossRef re-verification (Stage 4 anti-cheat).

    Overrides every metadata.json ref status with the CrossRef ground truth and
    fails closed if the non-arXiv real-existence rate falls below the floor.
    """
    audit = doi_audit.audit_run(run_dir)
    rate = audit.get("real_existence_rate")
    suspicious = set(audit.get("suspicious_dois") or [])

    meta_path = run_dir / "metadata.json"
    if meta_path.is_file():
        try:
            refs = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            refs = []
        if isinstance(refs, list):
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                doi = str(ref.get("doi") or "").strip()
                if not doi:
                    ref["status"] = "no_doi"
                elif doi in suspicious:
                    ref["status"] = "crossref_404_suspicious"  # override any claimed "verified"
                elif doi.lower().startswith("10.48550"):
                    ref["status"] = "arxiv_datacite"
                else:
                    ref["status"] = "crossref_real"
            meta_path.write_text(json.dumps(refs, indent=2, ensure_ascii=False), encoding="utf-8")

    audit["floor"] = DOI_REAL_RATE_FLOOR
    audit["passed"] = bool(rate is not None and rate >= DOI_REAL_RATE_FLOOR)
    (run_dir / "doi_audit.json").write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"doi_gate: real_existence_rate={rate} floor={DOI_REAL_RATE_FLOOR} passed={audit['passed']}", flush=True)
    return audit


# ---------------------------------------------------------------------------
# WS2 phase2 (a-side) — the contract carries a chat-produced DOI LIST (the
# subjective "which papers" choice). a does the deterministic part: a SINGLE
# CrossRef call per DOI both VERIFIES existence and COMPLETES canonical metadata
# (title/authors/year/journal), then builds references.bib by construction.
# Fake (CrossRef-404, non-arXiv) DOIs are dropped; the real-existence rate must
# clear the floor (fail-closed). a never trusts b's word — it re-derives every
# fact from CrossRef. No triple-source verify (that was the ~23-min cost), no
# model phase, no producer trust.
# ---------------------------------------------------------------------------

_LATEX_MAP = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "#": r"\#", "_": r"\_",
    "$": r"\$", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "{": r"\{", "}": r"\}",
}


def _bib_escape(value: Any) -> str:
    """Neutralise LaTeX specials in any free text reaching the render (defence in
    depth — a never trusts its input). Single pass over the ORIGINAL characters
    so the braces/backslashes the replacements introduce are not re-escaped."""
    s = re.sub(r"[\x00-\x1f\x7f]", " ", str(value))
    return "".join(_LATEX_MAP.get(ch, ch) for ch in s).strip()


def _safe_key(key: Any, idx: int) -> str:
    k = re.sub(r"[^A-Za-z0-9_:.-]", "", str(key or ""))
    return k or f"ref{idx}"


def _key_from(authors: list[str], year: str, idx: int) -> str:
    """Stable citekey when the contract didn't supply one: firstauthorYEAR."""
    surname = ""
    if authors:
        surname = re.sub(r"[^A-Za-z]", "", str(authors[0]).split(",")[0])
    return f"{(surname or 'ref').lower()}{year or idx}"


def contract_doi_candidates(contract: dict[str, Any]) -> list[dict[str, Any]]:
    """The chat-produced DOI list from a v2 contract (v1 -> []). Accepts
    literature.verified_refs[] ({key?,doi,...}) or literature.doi_list[]
    (strings or {key,doi}). The `verified` flag is ADVISORY — a re-verifies
    every DOI itself; only the doi (and optional key) are taken from the contract."""
    lit = contract.get("literature") or {}
    out: list[dict[str, Any]] = []
    for raw in (lit.get("verified_refs"), lit.get("doi_list")):
        if not isinstance(raw, list):
            continue
        for r in raw:
            if isinstance(r, str) and r.strip():
                out.append({"key": None, "doi": r.strip()})
            elif isinstance(r, dict) and str(r.get("doi") or "").strip():
                out.append({"key": r.get("key"), "doi": str(r["doi"]).strip()})
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for c in out:
        d = c["doi"].lower()
        if d not in seen:
            seen.add(d)
            uniq.append(c)
    return uniq


def build_refs_from_doi_list(run_dir: Path, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """a-side deterministic phase2: single-source CrossRef verify + complete every
    DOI, then write references.bib / metadata.json / doi_verification_report.md /
    doi_audit.json. Drops fabricated (CrossRef-404 non-arXiv) DOIs; fails closed if
    the real-existence rate is below the floor. Returns the audit summary."""
    seen_keys: set[str] = set()
    entries: list[str] = []
    meta: list[dict[str, Any]] = []
    real = suspicious = undet = arxiv = 0
    suspicious_dois: list[str] = []

    for i, c in enumerate(candidates):
        doi = str(c["doi"]).strip()
        is_arxiv = doi.lower().startswith("10.48550")
        status, m = doi_audit.fetch_crossref_meta(doi)
        time.sleep(0.12)  # polite
        if status == "404":
            if is_arxiv:
                arxiv += 1
                title, authors, year, journal, st = doi, [], "", "", "arxiv_datacite"
            else:
                suspicious += 1
                suspicious_dois.append(doi)
                continue  # fabricated DOI -> drop, never enters the paper
        elif status == "undet":
            undet += 1
            title, authors, year, journal, st = doi, [], "", "", "crossref_undetermined"
        else:  # ok
            real += 1
            title = m.get("title") or doi
            authors = m.get("authors") or []
            year = str(m.get("year") or "")
            journal = m.get("journal") or ""
            st = "crossref_real"

        key = base = _safe_key(c.get("key") or _key_from(authors, year, i), i)
        n = 1
        while key in seen_keys:
            n += 1
            key = f"{base}_{n}"
        seen_keys.add(key)

        fields = [f"  title = {{{_bib_escape(title)}}}"]
        author_field = " and ".join(_bib_escape(a) for a in authors if str(a).strip())
        if author_field:
            fields.append(f"  author = {{{author_field}}}")
        if year:
            fields.append(f"  year = {{{re.sub(r'[^0-9]', '', year) or year}}}")
        if journal:
            fields.append(f"  journal = {{{_bib_escape(journal)}}}")
        fields.append(f"  doi = {{{_bib_escape(doi)}}}")
        entries.append("@article{" + key + ",\n" + ",\n".join(fields) + "\n}\n")
        meta.append({"key": key, "doi": doi, "title": title, "authors": authors,
                     "year": year, "journal": journal, "status": st})

    (run_dir / "references.bib").write_text("\n".join(entries), encoding="utf-8")
    (run_dir / "metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    determinable = real + suspicious
    rate = round(real / determinable, 3) if determinable else None
    audit: dict[str, Any] = {
        "run": run_dir.name, "mode": "verify_and_complete",
        "candidates": len(candidates), "kept": len(meta),
        "crossref_real": real, "arxiv_on_datacite": arxiv,
        "suspicious_404": suspicious, "undetermined": undet,
        "suspicious_dois": suspicious_dois,
        "real_existence_rate": rate, "real_rate": rate,  # floor_score reads real_rate
        "floor": DOI_REAL_RATE_FLOOR,
    }
    # rate is None only when nothing was determinable (all arXiv / network down):
    # cannot judge fabrication -> do not fail closed on absence of evidence.
    audit["passed"] = bool(rate is None or rate >= DOI_REAL_RATE_FLOOR)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "doi_verification_report.md").write_text(
        "# DOI Verification (a-side single-source CrossRef verify + complete)\n\n"
        f"{len(candidates)} DOIs supplied by chat; {len(meta)} kept after CrossRef "
        f"verification ({real} real, {arxiv} arXiv, {suspicious} dropped as "
        f"fabricated, {undet} undetermined). Canonical title/authors/year/journal "
        "completed from CrossRef. real_existence_rate="
        f"{rate} (floor {DOI_REAL_RATE_FLOOR}).\n",
        encoding="utf-8")
    print(f"phase2(verify+complete): candidates={len(candidates)} kept={len(meta)} "
          f"real_rate={rate} passed={audit['passed']}", flush=True)
    return audit


# ---------------------------------------------------------------------------
# WS0 leftovers — post-run integrity: (1) verify the real results actually
# satisfy the contract's resolved experiment plan; (2) emit a provenance record
# so a run is reproducible/auditable (code commit, deps, seed, data, hashes).
# ---------------------------------------------------------------------------


def validate_experiment_result(contract: dict[str, Any], result: dict[str, Any]) -> list[str] | None:
    """Post-experiment gate: do the real results satisfy the resolved plan?
    Returns None for v1 / no-experiment contracts (nothing to validate against),
    else the (possibly empty) list of violations from capabilities."""
    plan = capabilities.validate_experiment_contract(contract)
    resolved = plan.get("resolved_plan")
    if not resolved:
        return None
    return capabilities.validate_real_results(result, resolved)


def _git_commit(path: Path) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:  # noqa: BLE001 - provenance is best-effort, never fatal
        return None


def _sha256_file(p: Path) -> str | None:
    if not p.is_file():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _dep_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {"python": platform.python_version()}
    for mod in ("numpy", "scipy", "sklearn", "pyarrow", "pandas"):
        try:
            out[mod] = getattr(__import__(mod), "__version__", None)
        except Exception:  # noqa: BLE001 - missing optional dep is just unknown
            out[mod] = None
    return out


def write_provenance(run_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Reproducibility record for the run: experiment-code commit, dependency
    versions, RNG seed, data source, and content hashes of the result + schema."""
    rr_path = run_dir / "real_experiments" / "real_results.json"
    real: dict[str, Any] = {}
    if rr_path.is_file():
        try:
            real = json.loads(rr_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            real = {}
    prov = {
        "schema_version": "provenance-2026-06-10",
        "job_id": contract.get("job_id"),
        "generated_at": now(),
        "experiment_code_commit": _git_commit(SCRIPT_DIR),
        "contract_schema_hash": contract.get("schema_hash"),
        "a_schema_hash": capabilities.schema_hash(),
        "deps": _dep_versions(),
        "seed": real.get("random_state"),
        "data_source": real.get("source"),
        "data_rows": real.get("rows"),
        "real_results_status": real.get("status"),
        "real_results_simulated": real.get("simulated"),
        "real_results_sha256": _sha256_file(rr_path),
    }
    (run_dir / "provenance.json").write_text(
        json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
    return prov


REVISION_ARTIFACTS = (
    "paper_draft_v0.qmd", "paper_draft_v0.pdf", "mvp_check_report.md", "paper_review_report.md",
    "elite_audit_report.md", "final_content_review_deterministic.json", "gate_report.json",
)


def archive_round(run_dir: Path, n: int) -> None:
    """Preserve a round's artifacts in history_round_N/ before it is overwritten."""
    archive = run_dir / f"history_round_{n}"
    archive.mkdir(parents=True, exist_ok=True)
    for name in REVISION_ARTIFACTS:
        src = run_dir / name
        if src.is_file():
            shutil.copy2(src, archive / name)


def rollback_round(run_dir: Path, n: int) -> None:
    """Restore the pre-round artifacts from history_round_N (the last good state).
    Used when a revision round regresses or crashes — never ship a worse version."""
    archive = run_dir / f"history_round_{n}"
    for name in REVISION_ARTIFACTS:
        src = archive / name
        if src.is_file():
            shutil.copy2(src, run_dir / name)


def build_revision_prompt(contract: dict[str, Any], lane: str, problems: list[dict[str, Any]],
                          real_summary: str | None) -> str:
    """Directive rewrite prompt: feed the actual parsed problems back (generic, not
    hardcoded) + the verbatim real metrics, with hard anti-truncation rules."""
    bullets = "\n".join(
        f"- [{p.get('severity', '?')}] {p.get('location', '')}: {p.get('description') or p.get('id')}"
        for p in problems if isinstance(p, dict)
    ) or "- (no structured problems parsed; fix any internal inconsistency vs the real results below)"
    body = f"""
Bounded task: REVISE the existing paper_draft_v0.qmd to resolve the review problems below. Read the
current paper_draft_v0.qmd from disk, edit it, and write the full updated manuscript back to
paper_draft_v0.qmd.

=== REVIEW PROBLEMS TO FIX (previous round) ===
{bullets}

=== HOW TO FIX ===
- Resolve EVERY problem above. For any claim that contradicts the real experiment, correct the prose to
  match the real data (e.g. if the data is a single filing year, describe cross-validation, not a
  multi-year temporal holdout).
- Make text, tables, figure captions, and any spec numbers mutually consistent.
- Do NOT introduce claims the real results do not support.

=== HARD RULES (do not regress) ===
- Keep the manuscript FULL-LENGTH and detailed (>3000 words). Do NOT truncate, summarise, or output a
  skeleton. Preserve all sections and all @-citations and @fig-/@tbl- references.
- CITATION KEYS ARE IMMUTABLE: every `[@key]` / `@key` citation must keep its EXACT key string
  (they bind to references.bib). Never rename, re-spell, translate, or delete a citation key;
  never invent a new key. If a sentence with a citation is rewritten, carry its citation keys
  over unchanged. A single changed key fails validation and the whole revision is rolled back.
- Keep the YAML frontmatter intact (title, author, bibliography, colorlinks/link-citations/citecolor).
- Do not touch anything between <!-- GENERATED:... --> and <!-- /GENERATED:... --> markers.
- Every table value must come from the real results; do not invent numbers.
Write the revised paper_draft_v0.qmd. Append one line to progress.md. Stop after revising.
"""
    if real_summary:
        body += "\n" + real_summary + "\n"
    return base_requirements(contract, lane) + body


COPILOT_BIN = os.environ.get("PAPER_COPILOT_BIN", "copilot")
# Pin the cheapest valid agentic-CLI model. All CLI models bill to the same
# `premium_interactions` quota (chat/completions are unlimited but unreachable from
# this CLI); the default `auto` picks a high-multiplier model (~9.5 credits/review),
# while claude-haiku-4.5 is far cheaper — many more reviews per monthly free-tier cap.
COPILOT_MODEL = os.environ.get("PAPER_COPILOT_MODEL", "claude-haiku-4.5")


def copilot_env() -> dict[str, str]:
    """Environment for the copilot subprocess: load COPILOT_GITHUB_TOKEN from ~/.env
    if not already set, and allow non-interactive tool use."""
    env = os.environ.copy()
    if not env.get("COPILOT_GITHUB_TOKEN"):
        envfile = Path.home() / ".env"
        if envfile.is_file():
            for line in envfile.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("COPILOT_GITHUB_TOKEN="):
                    env["COPILOT_GITHUB_TOKEN"] = line.split("=", 1)[1].strip()
                    break
    env["COPILOT_ALLOW_ALL"] = "1"
    return env


def copilot_available(env: dict[str, str]) -> bool:
    return bool(env.get("COPILOT_GITHUB_TOKEN")) and shutil.which(COPILOT_BIN) is not None


def build_copilot_review_prompt(contract: dict[str, Any], real_summary: str | None, elite: bool) -> str:
    elite_line = '  "desk_reject_probability": 0.0,\n' if elite else ""
    grounding = real_summary or "(read real_experiments/real_results.json for the real metrics)"
    return f"""Read paper_draft_v0.qmd (a research manuscript) and real_experiments/real_results.json in the
current directory. Act as a strict but fair journal reviewer for {contract.get('target_journal')}.

GROUND TRUTH — the experiment really ran; do NOT claim the data is missing, failed, or simulated:
{grounding}

Score 7 dimensions on a 1.0-10.0 scale, judging only what is written on the page: novelty,
methodological_rigor, evidence_validity, literature_grounding, result_interpretation,
limitation_honesty, writing_coherence.

Then produce a CONCRETE, EXECUTABLE revision TASK LIST. For each issue, copy the EXACT current text
from the manuscript into target_content and write the corrected text into replacement_content (a
verbatim find-and-replace the pipeline will apply). Keep replacements local and faithful; never drop
@-citations. severity: P0 = blocking/desk-reject (factual error, unsupported claim), P1 = should fix,
P2 = minor. verification.absent = a regex of the wrong text (must be gone after), verification.present
= a regex of the new text (must appear after).

Write a short markdown review, then END with exactly one fenced json block and nothing after it:
```json
{{"scores_7dim": {{"novelty": 0.0, "methodological_rigor": 0.0, "evidence_validity": 0.0, "literature_grounding": 0.0, "result_interpretation": 0.0, "limitation_honesty": 0.0, "writing_coherence": 0.0}},
{elite_line}  "tasks": [{{"id": "C1", "severity": "P1", "type": "value_swap", "target_section": "Results", "target_content": "<exact current text>", "replacement_content": "<corrected text>", "description": "why", "verification": {{"absent": "<regex of old>", "present": "<regex of new>"}}}}]}}
```
Replace every 0.0 and the example task with your real assessment. Use type "value_swap" when you can
give exact target+replacement text; use "block_rewrite" only when a whole passage must be rewritten."""


def _write_reviewer_status(run_dir: Path, status: str, reason: str = "") -> None:
    """Record whether the Engine B (Copilot) reviewer actually scored the paper.
    compile_review reads this to tell a real desk-reject apart from a reviewer outage."""
    (run_dir / "reviewer_status.json").write_text(
        json.dumps({"reviewer": "copilot", "status": status, "reason": reason},
                   ensure_ascii=False, indent=2), encoding="utf-8")


def run_copilot_review(run_dir: Path, contract: dict[str, Any], real_summary: str | None,
                       elite: bool, timeout_s: int = 600) -> list[dict[str, Any]]:
    """Engine B reviewer via Copilot (GPT-class, honest). Writes paper_review_report.md
    (scores_7dim + tasks) for compile_review, and RETURNS the revision tasks so the
    loop can apply them alongside Engine C's deterministic tasks."""
    prompt = build_copilot_review_prompt(contract, real_summary, elite)
    log_dir = run_dir / "_phase_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "review_copilot.prompt.txt").write_text(prompt, encoding="utf-8")
    try:
        proc = subprocess.run([COPILOT_BIN, "-p", prompt, "--model", COPILOT_MODEL], cwd=run_dir, env=copilot_env(),
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
        out = proc.stdout or ""
    except subprocess.TimeoutExpired:
        (log_dir / "review_copilot.stderr.txt").write_text("copilot review timed out", encoding="utf-8")
        _write_reviewer_status(run_dir, "unavailable", "timeout")
        return []
    (log_dir / "review_copilot.stdout.txt").write_text(out, encoding="utf-8")
    stderr = proc.stderr or ""
    if stderr:
        (log_dir / "review_copilot.stderr.txt").write_text(stderr[-2000:], encoding="utf-8")
    block = compile_review._last_json_block(out) or {}
    scores = block.get("scores_7dim") if isinstance(block.get("scores_7dim"), dict) else {}
    # Distinguish "reviewer ran out of quota / died mid-stream" from "reviewer judged
    # the paper". A 402 quota_exceeded (or any run that fails to emit all 7 dimensions)
    # must NOT collapse into a generic content P0 — it is an external-reviewer outage
    # the orchestrator should resolve out-of-band. See compile_review REVIEWER_UNAVAILABLE.
    if not all(d in scores for d in compile_review.SEVEN_DIMS):
        if "quota_exceeded" in stderr or "exceeded your monthly quota" in (stderr + out):
            reason = "quota_exceeded"
        elif proc.returncode != 0:
            reason = f"copilot_exit_{proc.returncode}"
        else:
            reason = "incomplete_review"
        _write_reviewer_status(run_dir, "unavailable", reason)
        print(f"review_copilot: UNAVAILABLE reason={reason} exit={proc.returncode}", flush=True)
        return []
    _write_reviewer_status(run_dir, "ok", "")
    if "```" in out:
        (run_dir / "paper_review_report.md").write_text(out, encoding="utf-8")
    tasks = [t for t in (block.get("tasks") or []) if isinstance(t, dict)]
    for t in tasks:
        t.setdefault("engine", "B")
        t.setdefault("type", "value_swap")
    (run_dir / "copilot_tasks.json").write_text(
        json.dumps({"tasks": tasks}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"review_copilot: exit={proc.returncode} tasks={len(tasks)} p0={sum(1 for t in tasks if t.get('severity')=='P0')}", flush=True)
    return tasks


CODEX_BIN = os.environ.get("PAPER_CODEX_BIN", "codex")
CODEX_AUTH_DIR = Path(os.environ.get("PAPER_CODEX_AUTH_DIR", str(Path.home() / ".codex")))


def codex_available() -> bool:
    return shutil.which(CODEX_BIN) is not None and (CODEX_AUTH_DIR / "auth.json").is_file()


def _rotate_codex_auth(log_dir: Path) -> bool:
    """Multi-account quota rotation: auth profiles live as auth.json.<name> next
    to the active auth.json. When the active account hits its usage limit, swap
    in the first profile whose content differs and let the caller retry. Returns
    False when no alternate account is available (single-account setups)."""
    active = CODEX_AUTH_DIR / "auth.json"
    current = active.read_bytes() if active.is_file() else b""
    for profile in sorted(CODEX_AUTH_DIR.glob("auth.json.*")):
        try:
            if profile.read_bytes() != current:
                shutil.copy2(profile, active)
                active.chmod(0o600)
                (log_dir / "codex_auth_rotation.txt").write_text(
                    f"rotated active codex auth to {profile.name}", encoding="utf-8")
                print(f"codex auth rotated -> {profile.name}", flush=True)
                return True
        except OSError:
            continue
    return False


def run_codex_review(run_dir: Path, contract: dict[str, Any], real_summary: str | None,
                     elite: bool, timeout_s: int = 900) -> list[dict[str, Any]]:
    """Engine B reviewer via Codex CLI (gpt-5.5 — the most honest reviewer in the
    harness benchmark). Same output contract as the Copilot path: prints a fenced
    JSON block with scores_7dim + tasks; we persist paper_review_report.md and
    return the revision tasks. Substitutes Copilot while its quota is dead.
    On a usage-limit failure the auth rotates to the next account profile
    (auth.json.<n>) and the review retries — once per available profile."""
    prompt = build_copilot_review_prompt(contract, real_summary, elite)
    log_dir = run_dir / "_phase_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "review_codex.prompt.txt").write_text(prompt, encoding="utf-8")
    max_attempts = 1 + len(list(CODEX_AUTH_DIR.glob("auth.json.*")))
    proc = None
    out = stderr = ""
    reason = "incomplete_review"
    for attempt in range(1, max_attempts + 1):
        try:
            proc = subprocess.run(
                [CODEX_BIN, "exec", "--skip-git-repo-check", "--sandbox", "read-only", prompt],
                cwd=run_dir, stdin=subprocess.DEVNULL, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
            out = proc.stdout or ""
        except subprocess.TimeoutExpired:
            (log_dir / "review_codex.stderr.txt").write_text("codex review timed out", encoding="utf-8")
            _write_reviewer_status(run_dir, "unavailable", "timeout")
            return []
        (log_dir / "review_codex.stdout.txt").write_text(out, encoding="utf-8")
        stderr = proc.stderr or ""
        if stderr:
            (log_dir / "review_codex.stderr.txt").write_text(stderr[-2000:], encoding="utf-8")
        combined = stderr + out
        if "hit your usage limit" in combined or "usage limit" in combined:
            reason = "quota_exceeded"
            if attempt < max_attempts and _rotate_codex_auth(log_dir):
                continue  # next account takes over
            break
        break  # success or a non-quota failure: no rotation retry
    block = compile_review._last_json_block(out) or {}
    scores = block.get("scores_7dim") if isinstance(block.get("scores_7dim"), dict) else {}
    if not all(d in scores for d in compile_review.SEVEN_DIMS):
        if reason != "quota_exceeded":
            reason = f"codex_exit_{proc.returncode}" if proc is not None and proc.returncode != 0 \
                else "incomplete_review"
        _write_reviewer_status(run_dir, "unavailable", reason)
        print(f"review_codex: UNAVAILABLE reason={reason}", flush=True)
        return []
    _write_reviewer_status(run_dir, "ok", "")
    if "```" in out:
        (run_dir / "paper_review_report.md").write_text(out, encoding="utf-8")
    tasks = [t for t in (block.get("tasks") or []) if isinstance(t, dict)]
    for t in tasks:
        t.setdefault("engine", "B")
        t.setdefault("type", "value_swap")
    (run_dir / "copilot_tasks.json").write_text(
        json.dumps({"tasks": tasks}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"review_codex: exit={proc.returncode} tasks={len(tasks)} p0={sum(1 for t in tasks if t.get('severity')=='P0')}", flush=True)
    return tasks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--model", default="big-pickle")
    ap.add_argument("--provider", default=None, help="override; else derived from --model")
    ap.add_argument("--lane", choices=["cpu-real", "mvp"], default="cpu-real")
    ap.add_argument("--review-depth", choices=["7dim", "7dim+elite", "full-3-layer"], default="7dim")
    ap.add_argument("--content-threshold", type=float, default=6.0)
    ap.add_argument("--max-revision-rounds", type=int, default=2,
                    help="review->revision iterations while P0s remain (Fix 2)")
    ap.add_argument("--timeout", type=int, default=2400, help="per-phase timeout seconds")
    ap.add_argument("--real-limit", type=int, default=2000)
    ap.add_argument("--phases", nargs="+", default=list(PAPER_PHASES))
    args = ap.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    contract = load_contract(run_dir)
    provider = provider_for(args.model, args.provider)
    trace: dict[str, Any] = {
        "driver": "paper_driver", "model": args.model, "provider": provider, "lane": args.lane,
        "review_depth": args.review_depth, "started_at": now(), "steps": [],
    }

    def record(step: str, **kw: Any) -> None:
        trace["steps"].append({"step": step, "at": now(), **kw})
        (run_dir / "newarch_trace.json").write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")

    elite = args.review_depth in {"7dim+elite", "full-3-layer"}
    real_summary: str | None = None

    def load_real_summary() -> str | None:
        """Real metrics block for phase7/8 prompts, from the just-run or prior result."""
        rp = run_dir / "real_experiments" / "real_results.json"
        if not rp.is_file():
            return None
        try:
            res = json.loads(rp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return metrics_block(res) if res.get("status") == "completed" else None

    phases = [p for p in args.phases if p in PAPER_PHASES]  # "none"/unknown => reviews-only
    doi_candidates = contract_doi_candidates(contract)
    for phase in phases:
        if phase == "phase2" and doi_candidates:
            # The contract carries chat's DOI list. a verifies + completes every
            # entry against CrossRef (single source) and builds the bib by
            # construction — no model phase, no producer trust.
            gate = build_refs_from_doi_list(run_dir, doi_candidates)
            record("phase2_verify_complete",
                   candidates=gate.get("candidates"), kept=gate.get("kept"),
                   real_existence_rate=gate.get("real_existence_rate"),
                   passed=gate.get("passed"), suspicious_404=gate.get("suspicious_404"))
            if not gate["passed"]:
                trace["final_status"] = "blocked_doi_gate"
                _write_blocked_review(run_dir, contract, args,
                    f"DOI gate failed: real rate {gate.get('real_existence_rate')} "
                    f"< {DOI_REAL_RATE_FLOOR}")
                return 3
            continue
        if phase == "phase7" and args.lane == "cpu-real":
            # Real-data step, dispatched by data_source.type: literature topics
            # collect + analyse the OpenAlex corpus (universal, any field); the
            # registered dataset lane (HUPD) runs the classical-ML experiment.
            ds_type = str((contract.get("data_source") or {}).get("type") or "").lower()
            if ds_type in ("meta-analysis", "meta_analysis"):
                result = run_meta_analysis_lane(run_dir, contract)
                record("meta_analysis", status=result.get("status"),
                       studies=((result.get("meta") or {}).get("prisma") or {}).get("studies_with_effects"),
                       simulated=result.get("simulated"))
                record("expand_references",
                       kept=expand_references_from_analysis(run_dir, contract, result))
            elif ds_type == "literature":
                result = run_scientometric_analysis(run_dir, contract)
                record("scientometric_analysis", status=result.get("status"),
                       rows=result.get("rows"), simulated=result.get("simulated"))
                record("expand_references",
                       kept=expand_references_from_analysis(run_dir, contract, result))
            else:
                result = run_real_experiment(run_dir, args.real_limit, max(args.timeout, 14400))
                record("real_experiment", status=result.get("status"), simulated=result.get("simulated"))
                # v2 contracts pin an experiment plan; the actual results must satisfy
                # it (status/simulated/expected keys/tasks) or the run is blocked.
                errs = validate_experiment_result(contract, result)
                if errs is not None:
                    record("experiment_validation", ok=not errs, errors=errs)
                    if errs:
                        trace["final_status"] = "blocked_experiment_validation"
                        _write_blocked_review(run_dir, contract, args,
                            "experiment results violate the resolved plan: " + "; ".join(errs))
                        return 3
            real_summary = metrics_block(result)
        if phase in {"phase7", "phase8"} and args.lane == "cpu-real" and real_summary is None:
            real_summary = load_real_summary()
        code = run_hermes(run_dir, phase, paper_prompt(phase, contract, args.lane, real_summary), args.model, provider, args.timeout)
        record(phase, exit=code)
        if code != 0:
            trace["final_status"] = f"failed_at_{phase}"
            record("abort", reason=f"{phase} did not produce required artifacts")
            return code
        if phase == "phase7":
            # Compile any TikZ figures the model authored into publication-quality png/svg.
            record("compile_tikz", figures=compile_tikz_figures(run_dir))
        if phase == "phase2":
            gate = doi_gate(run_dir)
            record("doi_gate", **{k: gate.get(k) for k in ("real_existence_rate", "passed", "suspicious_404")})
            if not gate["passed"]:
                trace["final_status"] = "blocked_doi_gate"
                _write_blocked_review(run_dir, contract, args, f"DOI gate failed: real rate {gate.get('real_existence_rate')} < {DOI_REAL_RATE_FLOOR}")
                return 3

    # Render + review + scoring only make sense once the full paper exists. This
    # guards partial --phases runs (and a phase8 that silently failed to emit QMD).
    if not (run_dir / "paper_draft_v0.qmd").is_file():
        trace["final_status"] = "no_paper_no_review"
        record("skip_review", reason="paper_draft_v0.qmd absent; skipping render + review")
        record("done")
        return 0

    # Deterministic results tables: replace `<!-- TABLE:tbl-* -->` placeholders with
    # numbers generated straight from real_results.json (correct-by-construction).
    try:
        contract_obj = json.loads((run_dir / "research_contract.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        contract_obj = {}
    record("inject_tables", n=tables.inject(run_dir, contract_obj))

    # Fix 1: deterministic journal-format render (replaces the model's ad-hoc render).
    record("render_pdf", ok=render_pdf(run_dir))
    rev_real = load_real_summary() if args.lane == "cpu-real" else None

    # Task-driven revision loop. Tasks come from Engine C (deterministic factual
    # gate) AND Engine B (Copilot reviewer — honest, also writes the score report).
    # value_swap tasks apply deterministically; block_rewrite via big-pickle. Every
    # round is validated and rolled back on regression/crash (never ship worse).
    cenv = copilot_env()
    use_copilot = copilot_available(cenv)

    # Reviewer cascade (full model reviewers, in trust order). Each entry is
    # tried once per gather; a quota-dead/unusable reviewer is popped and the
    # next takes over. When the cascade empties, the skilled big-pickle
    # fallback (verbatim-anchored tasks + floor-cross-checked scores) runs.
    reviewer_cascade: list[tuple[str, Any]] = []
    if use_copilot:
        reviewer_cascade.append(("copilot", run_copilot_review))
    if codex_available():
        reviewer_cascade.append(("codex", run_codex_review))
    fallback_active = not reviewer_cascade

    def _model_review_unusable() -> bool:
        # Reviewers mark quota/availability failures (402 etc.) in
        # reviewer_status.json; an "available" CLI that cannot actually score
        # must hand over to the next reviewer, not silently end the loop.
        rspath = run_dir / "reviewer_status.json"
        if rspath.is_file():
            try:
                if json.loads(rspath.read_text(encoding="utf-8")).get("status") == "unavailable":
                    return True
            except (json.JSONDecodeError, OSError):
                pass
        return not (run_dir / "paper_review_report.md").is_file()

    def run_skilled_fallback() -> list[dict[str, Any]]:
        # Engine B': skilled big-pickle reviewer subagents. Reports + scores come
        # from the review skills; the tasks pass converts findings into
        # verbatim-anchored revision tasks, and the mechanical filter drops
        # anything quoting text that does not exist (the known free-model
        # reviewer hallucination mode).
        for kind in ["review_mvp", "review_7dim", "review_tasks"] + (["review_elite"] if elite else []):
            run_hermes(run_dir, kind, review_prompt(kind, contract, args.lane),
                       args.model, provider, args.timeout)
        fb_tasks, fb_dropped = load_fallback_review_tasks(run_dir)
        record("fallback_review_tasks", kept=len(fb_tasks), dropped_hallucinated=fb_dropped)
        (run_dir / "reviewer_status.json").write_text(json.dumps({
            "status": "fallback_scored", "source": "big-pickle-skilled",
            "note": "copilot unavailable/quota-dead; skilled free-model reviewer with "
                    "verbatim-anchor task filter and floor cross-checked scores",
        }, indent=2), encoding="utf-8")
        return fb_tasks

    def gather_tasks() -> list[dict[str, Any]]:
        nonlocal fallback_active
        tasks = list(consistency_gate.run(run_dir).get("tasks", []))
        while reviewer_cascade and not fallback_active:
            name, review_fn = reviewer_cascade[0]
            got = review_fn(run_dir, contract, rev_real, elite)
            if not _model_review_unusable():
                tasks += got
                return tasks
            reviewer_cascade.pop(0)
            nxt = reviewer_cascade[0][0] if reviewer_cascade else "skilled-fallback"
            record(f"{name}_unusable_handover", next=nxt,
                   reason=f"{name} present but produced no usable review")
            if not reviewer_cascade:
                fallback_active = True
        if fallback_active:
            tasks += run_skilled_fallback()
        return tasks

    def p0(tasks: list[dict[str, Any]]) -> int:
        return sum(1 for t in tasks if t.get("severity") == "P0")

    def needs_round(tasks: list[dict[str, Any]]) -> bool:
        # Copilot rounds are spent on P0s only (credits). The free skilled
        # reviewer also iterates on P1s — master tier runs quality rounds
        # (typically 3, set by the router) until the task list dries up.
        if p0(tasks) > 0:
            return True
        return fallback_active and any(t.get("severity") == "P1" for t in tasks)

    # Resilient revision loop: a regressing round is rolled back but does NOT end
    # the loop. Degradation ladder per failure: (1) retry without block_rewrite
    # (the model rewrite is the usual cite-key breaker; value_swaps are exact),
    # (2) ban this round's tasks (content-keyed — review re-emits fresh ids) and
    # continue with whatever remains. The rounds budget bounds everything.
    banned: set[str] = set()
    skip_rewrites = False

    def _task_fingerprint(t: dict[str, Any]) -> str:
        return f"{t.get('type')}|{str(t.get('target_content') or t.get('description') or '')[:120]}"

    def active_of(ts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = [t for t in ts if _task_fingerprint(t) not in banned]
        if skip_rewrites:
            out = [t for t in out if t.get("type") != "block_rewrite"]
        return out

    tasks = gather_tasks()
    record("gather_tasks", p0=p0(tasks), n=len(tasks))
    active = active_of(tasks)
    round_idx = 0
    while needs_round(active) and round_idx < args.max_revision_rounds:
        round_idx += 1
        archive_round(run_dir, round_idx)
        before_cites = revision_tasks.cite_keys(
            (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8", errors="ignore"))
        block_tasks = [t for t in active if t.get("type") == "block_rewrite"]
        failed_reason = None
        try:
            swap = revision_tasks.apply_value_swaps(run_dir, active)
            record(f"value_swaps_r{round_idx}", applied=swap["applied"], unresolved=swap["unresolved"])
            if block_tasks:
                problems = [{
                    "severity": t["severity"], "location": t.get("target_section", ""),
                    "description": f"{t['description']} (locate and fix: {t.get('target_content', '')[:160]})",
                } for t in block_tasks]
                rc = run_hermes(run_dir, f"revision_r{round_idx}",
                                build_revision_prompt(contract, args.lane, problems, rev_real),
                                args.model, provider, args.timeout)
                record(f"revision_r{round_idx}", exit=rc)
            # Self-heal machine-owned tables: the model's revision may have touched
            # a GENERATED block (e.g. "fixing" an en-dash). inject() is idempotent —
            # it replaces any stale block with a fresh regeneration, so model edits
            # inside machine regions are healed rather than merely flagged P0.
            record(f"reinject_tables_r{round_idx}", n=tables.inject(run_dir, contract_obj))
            render_pdf(run_dir)
        except Exception as exc:  # noqa: BLE001 - any failure must roll back, not corrupt the run
            failed_reason = f"exception: {str(exc)[:200]}"
        if failed_reason is None:
            ok, metrics = revision_tasks.validation_gate(run_dir, before_cites=before_cites)
            record(f"validation_r{round_idx}", ok=ok, **metrics)
            if not ok:
                failed_reason = "validation regression"
        if failed_reason:
            rollback_round(run_dir, round_idx)
            if block_tasks and not skip_rewrites:
                skip_rewrites = True  # rung 1: same tasks, exact swaps only
                record(f"rollback_r{round_idx}", reason=failed_reason,
                       next_action="retry without block_rewrite (value_swap-only round)")
            else:
                banned |= {_task_fingerprint(t) for t in active}
                record(f"rollback_r{round_idx}", reason=failed_reason,
                       next_action=f"banned {len(active)} toxic tasks; continuing with the rest")
            active = active_of(tasks)
            continue
        # Successful round: model rewrites get another chance next round; bans stay.
        skip_rewrites = False
        tasks = gather_tasks()
        record(f"gather_tasks_r{round_idx}", p0=p0(tasks), n=len(tasks))
        active = active_of(tasks)

    # Final self-heal pass: if anything edited a GENERATED block after the last
    # inject (revision text pass, phase9 fixups), restore it and re-render so the
    # PDF matches the healed qmd. verify() then only fires on true tampering.
    healed = tables.inject(run_dir, contract_obj)
    if healed:
        record("reinject_tables_final", n=healed)
        record("render_pdf_after_heal", ok=render_pdf(run_dir))

    # Render-quality gate: inspect the actual PDF (the layer the content reviewer
    # never sees) so a broken render cannot pass with a high content score.
    rq = revision_tasks.render_quality_check(run_dir)
    (run_dir / "render_quality.json").write_text(
        json.dumps({"issues": rq}, indent=2, ensure_ascii=False), encoding="utf-8")
    record("render_quality", issues=len(rq), p0=sum(1 for i in rq if i.get("severity") == "P0"))

    # Final score artifact. gather_tasks already ran the Copilot review this round,
    # so paper_review_report.md + consistency_tasks.json reflect the latest draft.
    summary = compile_review.compile_reviews(run_dir, content_threshold=args.content_threshold, elite_required=elite)
    record("compile_review", mean_7dim=summary.get("mean_7dim"), p0=summary.get("p0_count"))

    prov = write_provenance(run_dir, contract)
    record("provenance", commit=prov.get("experiment_code_commit"),
           results_sha256=prov.get("real_results_sha256"), seed=prov.get("seed"))

    trace["final_status"] = "completed"
    trace["final_deterministic_score"] = summary.get("mean_7dim")
    trace["revision_rounds"] = round_idx
    trace["consistency_p0_final"] = p0(tasks)
    record("done")
    return 0


def _write_blocked_review(run_dir: Path, contract: dict[str, Any], args: Any, reason: str) -> None:
    """Emit a minimal artifact set so job_runner reports a clean blocked status."""
    review = {
        "mean_7dim": None, "scores_7dim": {}, "p0_count": 1, "p1_count": 0,
        "problems": [{"id": "DOI_GATE", "severity": "P0", "location": "references.bib",
                      "type": "fabricated_or_unverifiable_dois", "description": reason}],
        "elite": {"desk_reject_probability": None},
    }
    (run_dir / "final_content_review_deterministic.json").write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "gate_report.json").write_text(json.dumps({
        "no_p0": False, "p1_count": 0, "real_status": "blocked", "no_prose_skeleton": None,
        "prose_completeness_passed": None, "prose_total_words": None, "score_threshold": None,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
