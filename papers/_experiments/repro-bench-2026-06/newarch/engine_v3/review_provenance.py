"""Single source of truth for V3.2 review provenance validation.

Consumed by engine_v3.packs.paper (Gate R), acceptance_gate_v3.py, and
batch_validate_v3.py so the provenance rules cannot drift between the three.

V3_2_SPEC.md Decisions section is the authority:
- A pass-like review verdict must come from a Hermes domain-expert review with
  a capability decision trace, never from deterministic schema completion.
- The verdict is bound to the manuscript bytes it reviewed; content changes
  after review invalidate the verdict (see the 2026-07-02 audit: pass verdicts
  written at 13:16 were delivered against manuscripts rewritten at 14:25).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

REVIEW_METHOD_SCHEMA_VERSION = "paperlab.review_method.v3.2"
EXPECTED_DECISION_OWNER = "hermes"
EXPECTED_CAPABILITY_CLASS = "domain_expert_review"

# Reviewer identities that describe harness/deterministic machinery instead of
# an expert review. Matching is substring-based on purpose: any future label
# that self-describes as deterministic repair must stay untrusted.
UNTRUSTED_REVIEWER_MARKERS = (
    "deterministic",
    "fallback",
    "schema completion",
    "structural repair",
    "bounded final review",
    "diagnostic placeholder",
)

DECISION_TRACE_HEADING = "skill decision trace"

# Domain neutrality invariant (V3_2_SPEC.md Decisions D4): this module is
# engine-layer and must hold ZERO domain-specific artifact names. Each domain
# pack declares its own review/manuscript file names (see
# engine_v3/packs/paper_artifacts.py) and passes them in as parameters.
# Litmus: adding a new domain pack requires no change in this file.


def reviewer_is_untrusted(reviewer: Any) -> bool:
    text = str(reviewer or "").strip().lower()
    if not text:
        return True
    return any(marker in text for marker in UNTRUSTED_REVIEWER_MARKERS)


# Reviewers phrase success honestly ("cleared", round 5; "passed_after_repair",
# round 11). One vocabulary for every consumer: Gate R accepted the family but
# acceptance_gate kept its own hard-coded set and rejected the same record
# (batch job v3_0f6a0c83f9cf). Anything outside the family stays fail-closed.
REVIEW_STATUS_PASS_LIKE = ("passed", "pass", "done", "cleared", "ok")


def review_status_pass_like(status: Any) -> bool:
    text = str(status or "").strip().lower()
    return text in REVIEW_STATUS_PASS_LIKE or text.startswith("passed")


def manuscript_sha256(run_dir: Path | str, manuscript_files: tuple[str, ...] | list[str]) -> str:
    digest = hashlib.sha256()
    for rel in manuscript_files:
        path = Path(run_dir) / rel
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_review_method(review: Mapping[str, Any]) -> list[str]:
    method = review.get("review_method")
    if not isinstance(method, dict) or not method:
        return ["review_method provenance missing"]

    findings: list[str] = []
    if str(method.get("decision_owner") or "").strip().lower() != EXPECTED_DECISION_OWNER:
        findings.append(
            "review_method.decision_owner must be %r, got %r"
            % (EXPECTED_DECISION_OWNER, method.get("decision_owner"))
        )
    if str(method.get("capability_class") or "").strip() != EXPECTED_CAPABILITY_CLASS:
        findings.append(
            "review_method.capability_class must be %r, got %r"
            % (EXPECTED_CAPABILITY_CLASS, method.get("capability_class"))
        )
    if not str(method.get("selected_skill") or "").strip():
        findings.append("review_method.selected_skill missing")
    if not str(method.get("selection_reason") or "").strip():
        findings.append("review_method.selection_reason missing")
    if bool(method.get("vip_capability_required")) and method.get("vip_capability_available") is not True:
        findings.append("vip capability required but vip_capability_available is not true")
    inputs_checked = method.get("inputs_checked")
    if not isinstance(inputs_checked, list) or not [x for x in inputs_checked if str(x).strip()]:
        findings.append("review_method.inputs_checked missing or empty")
    return findings


def review_log_has_decision_trace(log_text: str | None) -> bool:
    return DECISION_TRACE_HEADING in str(log_text or "").lower()


def review_freshness_findings(
    review: Mapping[str, Any],
    current_manuscript_sha256: str | None,
) -> list[str]:
    method = review.get("review_method")
    method = method if isinstance(method, dict) else {}
    stamp = str(method.get("reviewed_manuscript_sha256") or "").strip()
    if not stamp:
        return ["review_method.reviewed_manuscript_sha256 missing; verdict cannot be bound to the manuscript"]
    current = str(current_manuscript_sha256 or "").strip()
    if current and stamp != current:
        return ["review verdict is stale: manuscript changed after the review was written"]
    return []


def validate_review_artifacts(
    run_dir: Path | str,
    *,
    review_file: str,
    review_log_file: str,
    manuscript_files: tuple[str, ...] | list[str],
) -> list[str]:
    """Provenance findings computed straight from a run directory.

    Entry point for domain validators (acceptance/batch) so their rules cannot
    drift from the review gate. Artifact names come from the domain pack.
    """
    import json

    run_path = Path(run_dir)
    review_path = run_path / review_file
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["missing or invalid %s" % review_file]
    if not isinstance(review, dict):
        return ["missing or invalid %s" % review_file]
    log_path = run_path / review_log_file
    log_text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.is_file() else ""
    return validate_review_record(
        review,
        current_manuscript_sha256=manuscript_sha256(run_path, manuscript_files),
        review_log_text=log_text,
    )


def validate_review_record(
    review: Mapping[str, Any],
    *,
    current_manuscript_sha256: str | None = None,
    review_log_text: str | None = None,
) -> list[str]:
    """All provenance findings for a review record. Empty means trustworthy."""
    findings: list[str] = []
    loop = review.get("review_loop")
    loop = loop if isinstance(loop, dict) else {}
    if reviewer_is_untrusted(loop.get("reviewer_model")):
        findings.append(
            "reviewer_model %r is deterministic/fallback machinery, not an expert review"
            % (loop.get("reviewer_model"),)
        )
    findings.extend(validate_review_method(review))
    findings.extend(review_freshness_findings(review, current_manuscript_sha256))
    if not review_log_has_decision_trace(review_log_text):
        findings.append("review log has no skill decision trace section")
    return findings
