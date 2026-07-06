"""Paper-domain review artifact names.

engine_v3 general modules (review_provenance, orchestrator helpers) must stay
domain-neutral: they take artifact names as parameters and hold zero
paper-specific strings. This module is the paper pack's single place to
declare those names; insurance / IFRS packs declare their own equivalents.

Litmus (agentic-systems rule): adding a new domain pack must require zero
changes in engine_v3/review_provenance.py.
"""

from __future__ import annotations

REVIEW_FILE = "quality_review_round1.json"
REVIEW_LOG_FILE = "quality_review_log.md"
MANUSCRIPT_FILES: tuple[str, ...] = ("paper_draft_v0.qmd",)
# Human-QA channel: only the operator may write or clear these; the runtime
# reverts any worker edit (round 10: Hermes self-cleared its own worklist).
OPERATOR_OWNED_FILES: tuple[str, ...] = ("operator_findings.md",)
