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

import compile_review
import consistency_gate
import doi_audit
import revision_tasks

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
- Use existing files in this directory as checkpoints. Do not redo completed phases
  unless required to repair consistency.
- Ask no questions. No emoji.
"""


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
    }
    return base_requirements(contract, lane).split("Rules:")[0] + bodies[kind]


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
    """Deterministic Springer-style render (Fix 1) — replaces the weak model's
    ad-hoc reportlab. Produces paper_draft_v0.pdf from paper_draft_v0.qmd."""
    qmd = run_dir / "paper_draft_v0.qmd"
    pdf = run_dir / "paper_draft_v0.pdf"
    if not qmd.is_file():
        return False
    log_dir = run_dir / "_phase_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
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
- Keep the YAML frontmatter intact (title, author, bibliography, colorlinks/link-citations/citecolor).
- Every table value must come from the real results; do not invent numbers.
Write the revised paper_draft_v0.qmd. Append one line to progress.md. Stop after revising.
"""
    if real_summary:
        body += "\n" + real_summary + "\n"
    return base_requirements(contract, lane) + body


COPILOT_BIN = os.environ.get("PAPER_COPILOT_BIN", "copilot")


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
        proc = subprocess.run([COPILOT_BIN, "-p", prompt], cwd=run_dir, env=copilot_env(),
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
        out = proc.stdout or ""
    except subprocess.TimeoutExpired:
        (log_dir / "review_copilot.stderr.txt").write_text("copilot review timed out", encoding="utf-8")
        return []
    (log_dir / "review_copilot.stdout.txt").write_text(out, encoding="utf-8")
    if proc.stderr:
        (log_dir / "review_copilot.stderr.txt").write_text(proc.stderr[-2000:], encoding="utf-8")
    if "```" in out:
        (run_dir / "paper_review_report.md").write_text(out, encoding="utf-8")
    block = compile_review._last_json_block(out) or {}
    tasks = [t for t in (block.get("tasks") or []) if isinstance(t, dict)]
    for t in tasks:
        t.setdefault("engine", "B")
        t.setdefault("type", "value_swap")
    (run_dir / "copilot_tasks.json").write_text(
        json.dumps({"tasks": tasks}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"review_copilot: exit={proc.returncode} tasks={len(tasks)} p0={sum(1 for t in tasks if t.get('severity')=='P0')}", flush=True)
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
        return real_metrics_block(res) if res.get("status") == "completed" else None

    phases = [p for p in args.phases if p in PAPER_PHASES]  # "none"/unknown => reviews-only
    for phase in phases:
        if phase == "phase7" and args.lane == "cpu-real":
            result = run_real_experiment(run_dir, args.real_limit, max(args.timeout, 14400))
            record("real_experiment", status=result.get("status"), simulated=result.get("simulated"))
            real_summary = real_metrics_block(result)
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

    # Fix 1: deterministic journal-format render (replaces the model's ad-hoc render).
    record("render_pdf", ok=render_pdf(run_dir))
    rev_real = load_real_summary() if args.lane == "cpu-real" else None

    # Task-driven revision loop. Tasks come from Engine C (deterministic factual
    # gate) AND Engine B (Copilot reviewer — honest, also writes the score report).
    # value_swap tasks apply deterministically; block_rewrite via big-pickle. Every
    # round is validated and rolled back on regression/crash (never ship worse).
    cenv = copilot_env()
    use_copilot = copilot_available(cenv)

    def gather_tasks() -> list[dict[str, Any]]:
        tasks = list(consistency_gate.run(run_dir).get("tasks", []))
        if use_copilot:
            tasks += run_copilot_review(run_dir, contract, rev_real, elite)
        else:
            for kind in ["review_mvp", "review_7dim"] + (["review_elite"] if elite else []):
                run_hermes(run_dir, kind, review_prompt(kind, contract, args.lane),
                           args.model, provider, args.timeout)
        return tasks

    def p0(tasks: list[dict[str, Any]]) -> int:
        return sum(1 for t in tasks if t.get("severity") == "P0")

    tasks = gather_tasks()
    record("gather_tasks", p0=p0(tasks), n=len(tasks))
    round_idx = 0
    while p0(tasks) > 0 and round_idx < args.max_revision_rounds:
        round_idx += 1
        archive_round(run_dir, round_idx)
        before_cites = revision_tasks.cite_keys(
            (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8", errors="ignore"))
        try:
            swap = revision_tasks.apply_value_swaps(run_dir, tasks)
            record(f"value_swaps_r{round_idx}", applied=swap["applied"], unresolved=swap["unresolved"])
            block_tasks = [t for t in tasks if t.get("type") == "block_rewrite"]
            if block_tasks:
                problems = [{
                    "severity": t["severity"], "location": t.get("target_section", ""),
                    "description": f"{t['description']} (locate and fix: {t.get('target_content', '')[:160]})",
                } for t in block_tasks]
                rc = run_hermes(run_dir, f"revision_r{round_idx}",
                                build_revision_prompt(contract, args.lane, problems, rev_real),
                                args.model, provider, args.timeout)
                record(f"revision_r{round_idx}", exit=rc)
            render_pdf(run_dir)
        except Exception as exc:  # noqa: BLE001 - any failure must roll back, not corrupt the run
            record(f"revision_r{round_idx}_error", error=str(exc)[:300])
            rollback_round(run_dir, round_idx)
            break
        ok, metrics = revision_tasks.validation_gate(run_dir, before_cites=before_cites)
        record(f"validation_r{round_idx}", ok=ok, **metrics)
        if not ok:
            rollback_round(run_dir, round_idx)
            record(f"rollback_r{round_idx}", reason="validation failed; restored last good version")
            break
        tasks = gather_tasks()
        record(f"gather_tasks_r{round_idx}", p0=p0(tasks), n=len(tasks))

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
