#!/usr/bin/env python3
"""Task applier + guardrails + validation gate for the task-driven revision loop.

Consumes the unified task schema (from consistency_gate Engine C, and later the
Engine B reviewer-agent). value_swap tasks are applied deterministically in
Python (no model); block_rewrite tasks are handled by the driver via a targeted
big-pickle revision. Every round is validated and rolled back on regression.

Guardrails (agy ENGINE_C_PLAN_REVIEW.md): whitespace-insensitive target match,
context-bounded unique replacement, HTML/control-code sanitisation, citation-key
preservation, prose word floor — using compile_review._qmd_prose_words (NOT
mechanical_check, which has no word count) and mechanical_check for cites/cells.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import compile_review
import mechanical_check

CITE_KEY = re.compile(r"@([A-Za-z0-9_:-]+)")
# strip any tag that is not <i>/<b>/</i>/</b> (block reportlab/HTML injection)
BAD_TAG = re.compile(r"</?(?!/?[ib]\s*>)[A-Za-z!/][^>]*>")


def cite_keys(text: str) -> set[str]:
    return set(CITE_KEY.findall(text))


def sanitize_replacement(text: str) -> str:
    return BAD_TAG.sub("", text)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def verify_task(qmd: str, task: dict[str, Any]) -> bool:
    """A task is satisfied when its 'absent' regex no longer matches and its
    'present' regex matches."""
    v = task.get("verification") or {}
    if v.get("absent") and re.search(v["absent"], qmd):
        return False
    if v.get("present") and not re.search(v["present"], qmd, re.IGNORECASE):
        return False
    return True


def apply_value_swap(qmd: str, task: dict[str, Any]) -> tuple[str, bool]:
    """Deterministic substring swap with whitespace-insensitive fallback. Returns
    (new_qmd, applied)."""
    target = task.get("target_content") or ""
    repl = sanitize_replacement(task.get("replacement_content") or "")
    if not target or not repl:
        return qmd, False
    if target in qmd:
        return qmd.replace(target, repl, 1), True
    pat = re.escape(_norm(target)).replace(r"\ ", r"\s+")
    m = re.search(pat, qmd)
    if m:
        return qmd[: m.start()] + repl + qmd[m.end():], True
    return qmd, False  # target not found -> unresolved (caller records it)


def apply_value_swaps(run_dir: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply all value_swap tasks deterministically. Returns {applied, unresolved}."""
    qmd_path = run_dir / "paper_draft_v0.qmd"
    text = qmd_path.read_text(encoding="utf-8", errors="ignore")
    applied, unresolved = [], []
    for t in tasks:
        if t.get("type") != "value_swap":
            continue
        text, ok = apply_value_swap(text, t)
        (applied if ok else unresolved).append(t.get("id"))
    qmd_path.write_text(text, encoding="utf-8")
    return {"applied": applied, "unresolved": unresolved}


def validation_gate(run_dir: Path, before_cites: set[str] | None = None,
                    min_words: int = 3000, min_cites: int = 35) -> tuple[bool, dict[str, Any]]:
    """Post-revision gate. Fails if the round regressed length, citations, table
    integrity, the PDF, or dropped citation keys."""
    qmd_path = run_dir / "paper_draft_v0.qmd"
    pdf = run_dir / "paper_draft_v0.pdf"
    if not qmd_path.is_file():
        return False, {"error": "no qmd"}
    text = qmd_path.read_text(encoding="utf-8", errors="ignore")
    words = compile_review._qmd_prose_words(run_dir)
    cites = mechanical_check.count_citations(text)
    empty = mechanical_check.detect_empty_cells(text)
    pdf_ok = pdf.is_file() and pdf.stat().st_size > 1000
    keys_ok = True
    if before_cites is not None:
        # allow a small drop but not a collapse (keep >= 90% of prior keys)
        kept = cite_keys(text) & before_cites
        keys_ok = len(kept) >= 0.9 * len(before_cites) if before_cites else True
    metrics = {"words": words, "cites": cites, "empty_cells": empty, "pdf_ok": pdf_ok, "cite_keys_ok": keys_ok}
    ok = words >= min_words and cites >= min_cites and empty == 0 and pdf_ok and keys_ok
    return ok, metrics
