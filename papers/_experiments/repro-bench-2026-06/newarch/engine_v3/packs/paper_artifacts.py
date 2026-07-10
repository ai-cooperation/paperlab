"""Paper-domain review artifact names.

engine_v3 general modules (review_provenance, orchestrator helpers) must stay
domain-neutral: they take artifact names as parameters and hold zero
paper-specific strings. This module is the paper pack's single place to
declare those names; insurance / IFRS packs declare their own equivalents.

Litmus (agentic-systems rule): adding a new domain pack must require zero
changes in engine_v3/review_provenance.py.
"""

from __future__ import annotations

import json
from pathlib import Path

REVIEW_FILE = "quality_review_round1.json"
REVIEW_LOG_FILE = "quality_review_log.md"
MANUSCRIPT_FILES: tuple[str, ...] = ("paper_draft_v0.qmd",)
# Human-QA channel: only the operator may write or clear these; the runtime
# reverts any worker edit (round 10: Hermes self-cleared its own worklist).
OPERATOR_OWNED_FILES: tuple[str, ...] = ("operator_findings.md",)


def review_manuscript_files(run_dir: Path | str) -> tuple[str, ...]:
    """The files a review verdict binds to (hash stamp + mtime freshness).

    ADR-001 §V4-C: on new-architecture runs the verdict binds to the SOURCES the
    reviewer/healer actually edits (paper_meta.json + abstract + sections) — the qmd
    is a GENERATED artifact, and binding to it made every deterministic re-assembly
    look like a post-review edit (the reviewed-out freshness-loop hole). Legacy runs
    (no paper_meta.json) keep the qmd stamp unchanged."""
    meta_path = Path(run_dir) / "paper_meta.json"
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return MANUSCRIPT_FILES
        if isinstance(meta, dict):
            abstract_ref = str(meta.get("abstract_ref") or "")
            order = [str(rel) for rel in meta.get("section_order") or [] if str(rel)]
            if abstract_ref and order:
                return ("paper_meta.json", abstract_ref, *order)
    return MANUSCRIPT_FILES
