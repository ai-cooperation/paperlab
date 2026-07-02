from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3 import review_provenance as rp

pytestmark = pytest.mark.unit


def _valid_review_method(**overrides):
    method = {
        "schema_version": "paperlab.review_method.v3.2",
        "decision_owner": "hermes",
        "capability_class": "domain_expert_review",
        "selected_skill": "paper-review-skill",
        "selection_reason": "The task requires a domain expert review before delivery.",
        "vip_capability_required": True,
        "vip_capability_available": True,
        "inputs_checked": [
            "paper_draft_v0.qmd",
            "references.bib",
            "real_experiments/real_results.json",
        ],
    }
    method.update(overrides)
    return method


def test_untrusted_reviewer_markers_are_rejected():
    assert rp.reviewer_is_untrusted("deterministic bounded final review") is True
    assert rp.reviewer_is_untrusted("hermes bounded final re-review fallback") is True
    assert rp.reviewer_is_untrusted("deterministic structural repair") is True
    assert rp.reviewer_is_untrusted("") is True
    assert rp.reviewer_is_untrusted(None) is True


def test_real_reviewer_models_are_trusted():
    assert rp.reviewer_is_untrusted("codex-reviewer") is False
    assert rp.reviewer_is_untrusted("gpt-5.5 expert reviewer") is False


def test_validate_review_method_missing_is_fatal():
    assert rp.validate_review_method({}) == ["review_method provenance missing"]
    assert rp.validate_review_method({"review_method": {}}) == [
        "review_method provenance missing"
    ]


def test_validate_review_method_accepts_complete_contract():
    review = {"review_method": _valid_review_method()}
    assert rp.validate_review_method(review) == []


def test_validate_review_method_rejects_wrong_owner_and_class():
    review = {
        "review_method": _valid_review_method(
            decision_owner="harness", capability_class="schema_completion"
        )
    }
    findings = rp.validate_review_method(review)
    assert any("decision_owner" in f for f in findings)
    assert any("capability_class" in f for f in findings)


def test_validate_review_method_blocks_when_vip_capability_unavailable():
    review = {
        "review_method": _valid_review_method(vip_capability_available=False)
    }
    findings = rp.validate_review_method(review)
    assert any("vip capability" in f.lower() for f in findings)


def test_validate_review_method_requires_selected_skill_and_inputs():
    review = {
        "review_method": _valid_review_method(selected_skill="", inputs_checked=[])
    }
    findings = rp.validate_review_method(review)
    assert any("selected_skill" in f for f in findings)
    assert any("inputs_checked" in f for f in findings)


def test_review_log_decision_trace_detection():
    good = "# Quality Review Log\n\n## Skill Decision Trace\n\n- visible: paper-review-skill, elite-reviewer-audit\n- selected: paper-review-skill\n"
    bad = "# Quality Review Log\n\nround 1 passed\n"
    assert rp.review_log_has_decision_trace(good) is True
    assert rp.review_log_has_decision_trace(bad) is False
    assert rp.review_log_has_decision_trace("") is False


def test_manuscript_sha256_changes_with_content(tmp_path: Path):
    (tmp_path / "paper_draft_v0.qmd").write_text("version one", encoding="utf-8")
    first = rp.manuscript_sha256(tmp_path, ("paper_draft_v0.qmd",))
    (tmp_path / "paper_draft_v0.qmd").write_text("version two", encoding="utf-8")
    second = rp.manuscript_sha256(tmp_path, ("paper_draft_v0.qmd",))
    assert first and second and first != second


def test_freshness_requires_stamp_and_match(tmp_path: Path):
    (tmp_path / "paper_draft_v0.qmd").write_text("reviewed content", encoding="utf-8")
    current = rp.manuscript_sha256(tmp_path, ("paper_draft_v0.qmd",))

    no_stamp = {"review_method": _valid_review_method()}
    assert any(
        "reviewed_manuscript_sha256" in f
        for f in rp.review_freshness_findings(no_stamp, current)
    )

    fresh = {
        "review_method": _valid_review_method(reviewed_manuscript_sha256=current)
    }
    assert rp.review_freshness_findings(fresh, current) == []

    stale = {
        "review_method": _valid_review_method(reviewed_manuscript_sha256="0" * 64)
    }
    assert any("stale" in f for f in rp.review_freshness_findings(stale, current))


def test_validate_review_record_composes_all_checks(tmp_path: Path):
    (tmp_path / "paper_draft_v0.qmd").write_text("reviewed content", encoding="utf-8")
    current = rp.manuscript_sha256(tmp_path, ("paper_draft_v0.qmd",))
    review = {
        "review_loop": {"reviewer_model": "deterministic bounded final review"},
        "review_method": _valid_review_method(reviewed_manuscript_sha256=current),
    }
    findings = rp.validate_review_record(
        review,
        current_manuscript_sha256=current,
        review_log_text="## Skill Decision Trace\nselected: paper-review-skill\n",
    )
    assert any("reviewer" in f.lower() for f in findings)

    trusted = {
        "review_loop": {"reviewer_model": "codex-reviewer"},
        "review_method": _valid_review_method(reviewed_manuscript_sha256=current),
    }
    assert (
        rp.validate_review_record(
            trusted,
            current_manuscript_sha256=current,
            review_log_text="## Skill Decision Trace\nselected: paper-review-skill\n",
        )
        == []
    )

    no_trace = rp.validate_review_record(
        trusted,
        current_manuscript_sha256=current,
        review_log_text="round 1 passed\n",
    )
    assert any("decision trace" in f.lower() for f in no_trace)
