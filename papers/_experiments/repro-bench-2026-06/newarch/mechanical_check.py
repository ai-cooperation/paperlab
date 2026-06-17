#!/usr/bin/env python3
"""Layer 1 objective scorer for the paper-draft reproduction benchmark.

Scans one producer run directory and emits a JSON scorecard of the
paper-draft skill's hard requirements. Purely mechanical -- no LLM judgement.

Usage:
    python3 mechanical_check.py <run_dir> [<run_dir> ...]
    python3 mechanical_check.py --all   # all dirs under runs/
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Hard-requirement thresholds taken from paper-draft/SKILL.md
MIN_CITATIONS = 35
MIN_FIGURES = 3
MIN_TABLES = 2
MIN_FIG_TABLE_TOTAL = 5
MIN_BIB = 35


def find_qmd(run_dir: Path) -> Path | None:
    cands = sorted(run_dir.glob("*.qmd"))
    if not cands:
        return None
    # prefer the canonical filename
    for c in cands:
        if c.name == "paper_draft_v0.qmd":
            return c
    return cands[0]


def count_citations(qmd_text: str) -> int:
    """Count distinct in-text @citekey references (Pandoc style)."""
    # @key or [@key] -- exclude emails by requiring preceding non-word boundary
    keys = re.findall(r"(?<![\w/])@([a-zA-Z][\w:-]+)", qmd_text)
    # drop cross-ref targets (fig-, tbl-, eq-, sec-) which are not citations
    cites = [k for k in keys if not re.match(r"(fig|tbl|eq|sec|lst|thm)-", k)]
    return len(set(cites))


def count_fig_refs(qmd_text: str) -> int:
    return len(set(re.findall(r"@(fig-[\w:-]+)", qmd_text)))


def count_tables(qmd_text: str) -> int:
    """Count tables: explicit #tbl- labels OR markdown pipe-table blocks."""
    labelled = len(set(re.findall(r"#(tbl-[\w:-]+)", qmd_text)))
    if labelled:
        return labelled
    # fallback: count header separator rows like |---|---|
    return len(re.findall(r"\n\s*\|[\s:|-]+\|\s*\n", qmd_text))


def check_frontmatter(qmd_text: str) -> dict:
    head = qmd_text.split("---", 2)
    fm = head[1] if len(head) >= 3 else ""
    return {
        "colorlinks": "colorlinks: true" in fm,
        "link-citations": "link-citations: true" in fm,
        "citecolor": "citecolor:" in fm,
    }


def scan_figures(run_dir: Path) -> dict:
    figdir = run_dir / "figures"
    svgs = {p.stem for p in figdir.glob("*.svg")} if figdir.is_dir() else set()
    pngs = {p.stem for p in figdir.glob("*.png")} if figdir.is_dir() else set()
    paired = svgs & pngs
    return {
        "svg_count": len(svgs),
        "png_count": len(pngs),
        "paired_svg_png": len(paired),
    }


def scan_bib(run_dir: Path) -> dict:
    bib = run_dir / "references.bib"
    if not bib.is_file():
        return {"entries": 0, "with_abstract": 0}
    text = bib.read_text(encoding="utf-8", errors="ignore")
    entries = len(re.findall(r"^@\w+\s*\{", text, re.MULTILINE))
    abstracts = len(re.findall(r"\babstract\s*=", text, re.IGNORECASE))
    return {"entries": entries, "with_abstract": abstracts}


def detect_empty_cells(qmd_text: str) -> int:
    """Rough count of empty cells in pipe tables (|  | or | | )."""
    empty = 0
    for line in qmd_text.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and "---" not in s:
            cells = [c.strip() for c in s.strip("|").split("|")]
            empty += sum(1 for c in cells if c == "")
    return empty


def score_run(run_dir: Path) -> dict:
    run_dir = run_dir.resolve()
    qmd = find_qmd(run_dir)
    result: dict = {
        "run": run_dir.name,
        "qmd_exists": qmd is not None,
        "pdf_exists": (run_dir / "paper_draft_v0.pdf").is_file()
        or bool(list(run_dir.glob("*.pdf"))),
        "doi_report_exists": (run_dir / "doi_verification_report.md").is_file(),
        "progress_exists": (run_dir / "progress.md").is_file(),
    }
    bib = scan_bib(run_dir)
    figs = scan_figures(run_dir)
    result["bib_entries"] = bib["entries"]
    result["bib_with_abstract"] = bib["with_abstract"]
    result["figures"] = figs

    if qmd is not None:
        text = qmd.read_text(encoding="utf-8", errors="ignore")
        result["citations"] = count_citations(text)
        result["fig_refs"] = count_fig_refs(text)
        result["tables"] = count_tables(text)
        result["empty_cells"] = detect_empty_cells(text)
        result["frontmatter"] = check_frontmatter(text)
        result["qmd_bytes"] = len(text)
    else:
        result.update(
            citations=0, fig_refs=0, tables=0, empty_cells=0,
            frontmatter={}, qmd_bytes=0,
        )

    # Pass/fail gates + a 0-100 objective score
    checks = {
        "cite>=35": result["citations"] >= MIN_CITATIONS,
        "figs>=3(paired)": figs["paired_svg_png"] >= MIN_FIGURES,
        "tables>=2": result["tables"] >= MIN_TABLES,
        "figtbl>=5": (figs["paired_svg_png"] + result["tables"]) >= MIN_FIG_TABLE_TOTAL,
        "bib>=35": bib["entries"] >= MIN_BIB,
        "all_bib_abstract": bib["entries"] > 0 and bib["with_abstract"] >= bib["entries"],
        "doi_report": result["doi_report_exists"],
        "qmd_exists": result["qmd_exists"],
        "no_empty_cells": result["empty_cells"] == 0,
        "fm_colorlinks": result.get("frontmatter", {}).get("colorlinks", False),
    }
    result["checks"] = checks
    result["objective_score"] = round(100 * sum(checks.values()) / len(checks))
    return result


def main(argv: list[str]) -> int:
    base = Path(__file__).resolve().parent
    if not argv or argv[0] == "--all":
        dirs = sorted(p for p in (base / "runs").iterdir() if p.is_dir())
    else:
        dirs = [Path(a) for a in argv]
    out = [score_run(d) for d in dirs]
    print(json.dumps(out, indent=2, ensure_ascii=False))
    scores_path = base / "scores" / "mechanical_check.json"
    scores_path.parent.mkdir(exist_ok=True)
    scores_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
