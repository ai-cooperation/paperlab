"""Authoritative review-provenance backfill + review_heal engine_defect loop.

Origin: job v3_a4d6b4a714d2 (2026-07-11, sleep paper). The run really passed a
Hermes domain-expert review (11 hermes-codex delegations, decision trace in the
log, p0=0, delivery=pass, floor 85, all seven dimensions), but the review agent
wrote the model name only at the TOP LEVEL ``reviewer_model`` and left the field
Gate R actually reads — ``review_loop.reviewer_model`` — at None (with
fixer_model=None, floor_failed=None). ``reviewer_is_untrusted(None)`` is True, so
Gate R's one remaining provenance finding fail-closed the job, and 8 healer
rounds could not touch a field the review runtime owns.

The trap: the top-level ``reviewer_model`` string self-describes as
"...not deterministic fallback", which itself contains the UNTRUSTED markers
"deterministic"/"fallback" — copying it would fail-close again. The authoritative
model source is the engine's OWN runtime record: the dossier review_heal
delegations (runtime "hermes-codex"), which carries no untrusted marker.

Two behaviours are tested:
  A. authoritative backfill (fail-closed-safe): only a genuine hermes review with
     complete provenance gets the loop reviewer/fixer backfilled from the runtime;
     a record without that evidence keeps reviewer_model None and Gate R keeps
     blocking.
  B. review_heal defect_classifier: a Gate R block that is ONLY
     provenance-plumbing (p0=0, delivery pass, floor over the bar, dimensions ok,
     review_method valid, decision trace present, and only a reviewer_model-class
     provenance finding) is the engine's own bug — classify it as engine_defect
     instead of burning healer rounds. A real quality block (p0>0 or revise) is
     not the engine's bug.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3 import review_provenance
from engine_v3.core import run_gates
from engine_v3.core.contracts import GateReport, GateResult, GateSeverity
from engine_v3.packs.paper import PaperPack
from engine_v3.pipelines import paper as paper_pipeline

pytestmark = pytest.mark.unit


_DECISION_TRACE_LOG = (
    "# Quality review log\n\n## Skill Decision Trace\n\n"
    "- selected: paper-review-skill\n"
)


def _valid_review_method(**overrides):
    method = {
        "schema_version": "paperlab.review_method.v3.2",
        "decision_owner": "hermes",
        "capability_class": "domain_expert_review",
        "selected_skill": "paper-draft (hermes-agent skill bundle)",
        "selection_reason": "domain expert review before delivery",
        "vip_capability_required": True,
        "vip_capability_available": True,
        "inputs_checked": ["paper_draft_v0.qmd", "references.bib"],
        "reviewed_manuscript_sha256": "f" * 64,
    }
    method.update(overrides)
    return method


def _real_review_dimensions():
    return {
        "academic_rigor": {"score": 8.6},
        "novelty_positioning": {"score": 8.4},
        "experimental_completeness": {"score": 8.2},
        "writing_quality": {"score": 8.5},
        "practical_feasibility": {"score": 8.7},
        "citation_accuracy": {"score": 8.8},
        "format_compliance": {"score": 8.6},
    }


def _v3_a4d6b4a714d2_review():
    """The exact shape that fail-closed the sleep paper: a genuine review whose
    loop.reviewer_model / fixer_model / floor_failed the agent left unset, plus a
    top-level reviewer_model that self-describes with untrusted markers."""
    return {
        "p0_count": 0,
        "delivery": "pass",
        "floor_100": 85.0,
        "reviewer_model": (
            "big-pickle via Hermes Agent (repair attempt 8, domain-expert review "
            "pass after manuscript repair; not deterministic fallback)"
        ),
        "review_method": _valid_review_method(),
        "review_loop": {
            "status": "completed_pass",
            "rounds": 1,
            "reviewer_model": None,
            "fixer_model": None,
            "floor_failed": None,
            "independent_reviewer": True,
        },
        "dimensions": _real_review_dimensions(),
        "findings": [],
    }


def _write_review(run_dir: Path, review: dict) -> None:
    (run_dir / "quality_review_round1.json").write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # A genuine review leaves its skill decision trace in the log; write it by
    # default so tests exercise the real evidence path. Tests that assert the
    # no-trace fail-closed overwrite this file afterward.
    (run_dir / "quality_review_log.md").write_text(_DECISION_TRACE_LOG, encoding="utf-8")


def _write_dossier_with_review_heal_delegations(run_dir: Path, runtime: str = "hermes-codex") -> None:
    dossier = {
        "version": 3,
        "job_id": "v3_a4d6b4a714d2",
        "domain": "paper",
        "phases": {"review_heal": "blocked"},
        "artifacts": {},
        "evidence": {},
        "gate_reports": [],
        "delegations": [
            {"task_id": "review_heal:brain", "phase": "review_heal", "runtime": runtime, "class": "brain", "status": "blocked"},
            {"task_id": "review_heal:repair:8", "phase": "review_heal", "runtime": runtime, "class": "brain", "status": "ok"},
        ],
    }
    (run_dir / "dossier.v3.json").write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _stamp_manuscript(run_dir: Path, review: dict) -> str:
    """Write minimal manuscript files and stamp the review to the current bytes,
    so freshness findings don't mask the reviewer_model finding under test."""
    (run_dir / "paper_meta.json").write_text(
        json.dumps({"abstract_ref": "sections/00_abstract.md", "section_order": ["sections/introduction.md"]}),
        encoding="utf-8",
    )
    (run_dir / "sections").mkdir(exist_ok=True)
    (run_dir / "sections" / "00_abstract.md").write_text("Abstract.", encoding="utf-8")
    (run_dir / "sections" / "introduction.md").write_text("Intro.", encoding="utf-8")
    sha = review_provenance.manuscript_sha256(
        run_dir, ("paper_meta.json", "sections/00_abstract.md", "sections/introduction.md")
    )
    review["review_method"]["reviewed_manuscript_sha256"] = sha
    return sha


# --- A. authoritative backfill ---------------------------------------------


def test_backfill_fills_loop_reviewer_from_runtime_on_genuine_review(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review = _v3_a4d6b4a714d2_review()
    _stamp_manuscript(run_dir, review)
    _write_review(run_dir, review)
    _write_dossier_with_review_heal_delegations(run_dir)

    changed = paper_pipeline._backfill_review_provenance_from_runtime(run_dir)
    assert changed is True

    healed = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    loop = healed["review_loop"]
    assert loop["reviewer_model"] == "hermes-codex"
    assert loop["fixer_model"] == "hermes-codex"
    assert review_provenance.reviewer_is_untrusted(loop["reviewer_model"]) is False
    # floor_failed only becomes False on validator truth (floor present + no p0).
    assert loop["floor_failed"] is False
    # status normalized to a pass-like value the loop check accepts.
    assert review_provenance.review_status_pass_like(loop["status"]) is True


def test_backfilled_record_passes_gate_r_provenance(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review = _v3_a4d6b4a714d2_review()
    sha = _stamp_manuscript(run_dir, review)
    _write_review(run_dir, review)
    _write_dossier_with_review_heal_delegations(run_dir)

    paper_pipeline._backfill_review_provenance_from_runtime(run_dir)
    healed = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))

    report = run_gates(
        PaperPack(),
        {
            "review": healed,
            "review_log_present": True,
            "review_log_text": _DECISION_TRACE_LOG,
            "manuscript_sha256": sha,
        },
        only={"R"},
    )
    assert report.blocked is False, report.results[0].details


def test_backfill_never_uses_top_level_free_text_reviewer_model(tmp_path: Path) -> None:
    """The top-level reviewer_model contains "deterministic"/"fallback"; the
    backfill must draw from the runtime, never that untrusted free text."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review = _v3_a4d6b4a714d2_review()
    _stamp_manuscript(run_dir, review)
    _write_review(run_dir, review)
    _write_dossier_with_review_heal_delegations(run_dir)

    paper_pipeline._backfill_review_provenance_from_runtime(run_dir)
    healed = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    assert "deterministic" not in str(healed["review_loop"]["reviewer_model"]).lower()
    assert "fallback" not in str(healed["review_loop"]["reviewer_model"]).lower()


# --- A. fail-closed保命 ------------------------------------------------------


def test_backfill_refuses_when_review_method_incomplete(tmp_path: Path) -> None:
    """No genuine hermes review evidence (capability_class not domain_expert) →
    no authoritative source to backfill → loop.reviewer_model stays None and
    Gate R keeps blocking. Un-reviewed manuscripts never pass."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review = _v3_a4d6b4a714d2_review()
    review["review_method"]["capability_class"] = "schema_completion"
    sha = _stamp_manuscript(run_dir, review)
    _write_review(run_dir, review)
    _write_dossier_with_review_heal_delegations(run_dir)

    changed = paper_pipeline._backfill_review_provenance_from_runtime(run_dir)
    assert changed is False

    healed = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    assert healed["review_loop"]["reviewer_model"] is None

    report = run_gates(
        PaperPack(),
        {
            "review": healed,
            "review_log_present": True,
            "review_log_text": _DECISION_TRACE_LOG,
            "manuscript_sha256": sha,
        },
        only={"R"},
    )
    assert report.blocked is True


def test_backfill_refuses_when_no_decision_trace_in_log(tmp_path: Path) -> None:
    """A review_method may look complete but if the review log carries no skill
    decision trace, there is no proof a real review ran — no backfill."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review = _v3_a4d6b4a714d2_review()
    _stamp_manuscript(run_dir, review)
    _write_review(run_dir, review)
    _write_dossier_with_review_heal_delegations(run_dir)
    (run_dir / "quality_review_log.md").write_text("# log\nround 1 done\n", encoding="utf-8")

    changed = paper_pipeline._backfill_review_provenance_from_runtime(run_dir)
    assert changed is False
    healed = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    assert healed["review_loop"]["reviewer_model"] is None


def test_backfill_refuses_without_runtime_delegation_evidence(tmp_path: Path) -> None:
    """Genuine review_method but the dossier has no review_heal delegation →
    there is no authoritative runtime model to copy → stays None."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review = _v3_a4d6b4a714d2_review()
    _stamp_manuscript(run_dir, review)
    _write_review(run_dir, review)
    # dossier with unrelated delegations only
    (run_dir / "dossier.v3.json").write_text(
        json.dumps({
            "job_id": "j", "domain": "paper", "phases": {}, "artifacts": {}, "evidence": {},
            "gate_reports": [],
            "delegations": [
                {"task_id": "write:brain", "phase": "write", "runtime": "hermes-codex", "status": "ok"}
            ],
        }),
        encoding="utf-8",
    )

    changed = paper_pipeline._backfill_review_provenance_from_runtime(run_dir)
    assert changed is False
    healed = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    assert healed["review_loop"]["reviewer_model"] is None


def test_backfill_refuses_when_delegation_runtime_is_untrusted(tmp_path: Path) -> None:
    """If the review_heal runtime name itself carries an untrusted marker, it is
    not a trustworthy authoritative source — do not copy it."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review = _v3_a4d6b4a714d2_review()
    _stamp_manuscript(run_dir, review)
    _write_review(run_dir, review)
    _write_dossier_with_review_heal_delegations(run_dir, runtime="deterministic-fallback")

    changed = paper_pipeline._backfill_review_provenance_from_runtime(run_dir)
    assert changed is False
    healed = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    assert healed["review_loop"]["reviewer_model"] is None


def test_backfill_keeps_floor_failed_none_when_floor_absent(tmp_path: Path) -> None:
    """floor_failed is set to False ONLY on validator truth. If there is no floor
    score, the backfill must not assert the floor passed."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    review = _v3_a4d6b4a714d2_review()
    review.pop("floor_100", None)
    _stamp_manuscript(run_dir, review)
    _write_review(run_dir, review)
    _write_dossier_with_review_heal_delegations(run_dir)

    paper_pipeline._backfill_review_provenance_from_runtime(run_dir)
    healed = json.loads((run_dir / "quality_review_round1.json").read_text(encoding="utf-8"))
    assert healed["review_loop"]["floor_failed"] is not False


# --- B. review_heal defect_classifier ---------------------------------------


def _gate_r_result(*, passed: bool, evidence: dict) -> GateResult:
    return GateResult(
        gate_id="R",
        passed=passed,
        severity=GateSeverity.BLOCK,
        details="review failed" if not passed else "review passed",
        evidence=evidence,
    )


def _provenance_plumbing_block() -> GateReport:
    """A Gate R block whose ONLY failure is a reviewer_model-class provenance
    finding: everything else the gate reads is clean."""
    return GateReport(results=[_gate_r_result(
        passed=False,
        evidence={
            "p0_count": 0,
            "delivery": "pass",
            "floor_100": 85.0,
            "dimensions": {k: 8.5 for k in [
                "academic_rigor", "novelty_positioning", "experimental_completeness",
                "writing_quality", "practical_feasibility", "citation_accuracy",
                "format_compliance",
            ]},
            "review_log_present": True,
            "provenance_findings": [
                "reviewer_model None is deterministic/fallback machinery, not an expert review"
            ],
        },
    )])


def test_review_heal_classifier_flags_pure_provenance_plumbing(tmp_path: Path) -> None:
    review = _v3_a4d6b4a714d2_review()
    _write_review(tmp_path, review)
    (tmp_path / "quality_review_log.md").write_text(_DECISION_TRACE_LOG, encoding="utf-8")

    info = paper_pipeline._classify_review_heal_engine_defect(tmp_path, _provenance_plumbing_block())
    assert info is not None
    assert info["class"] == "engine_defect"
    assert info["phase"] == "review_heal"
    assert "engine_fingerprint" in info


def test_review_heal_classifier_ignores_real_p0_block(tmp_path: Path) -> None:
    review = _v3_a4d6b4a714d2_review()
    _write_review(tmp_path, review)
    (tmp_path / "quality_review_log.md").write_text(_DECISION_TRACE_LOG, encoding="utf-8")

    block = GateReport(results=[_gate_r_result(
        passed=False,
        evidence={
            "p0_count": 2,
            "delivery": "revise",
            "floor_100": 61.0,
            "dimensions": {},
            "review_log_present": True,
            "provenance_findings": ["reviewer_model None is deterministic/fallback machinery"],
        },
    )])
    assert paper_pipeline._classify_review_heal_engine_defect(tmp_path, block) is None


def test_review_heal_classifier_ignores_revise_delivery(tmp_path: Path) -> None:
    review = _v3_a4d6b4a714d2_review()
    _write_review(tmp_path, review)
    (tmp_path / "quality_review_log.md").write_text(_DECISION_TRACE_LOG, encoding="utf-8")

    block = GateReport(results=[_gate_r_result(
        passed=False,
        evidence={
            "p0_count": 0,
            "delivery": "revise",
            "floor_100": 85.0,
            "dimensions": {k: 8.5 for k in [
                "academic_rigor", "novelty_positioning", "experimental_completeness",
                "writing_quality", "practical_feasibility", "citation_accuracy",
                "format_compliance",
            ]},
            "review_log_present": True,
            "provenance_findings": ["reviewer_model None is deterministic/fallback machinery"],
        },
    )])
    assert paper_pipeline._classify_review_heal_engine_defect(tmp_path, block) is None


def test_review_heal_classifier_ignores_non_reviewer_model_provenance(tmp_path: Path) -> None:
    """A provenance finding that is NOT the reviewer_model-plumbing class (e.g. a
    stale-verdict / pending-content finding) is a real content problem the healer
    can still act on — not an engine defect."""
    review = _v3_a4d6b4a714d2_review()
    _write_review(tmp_path, review)
    (tmp_path / "quality_review_log.md").write_text(_DECISION_TRACE_LOG, encoding="utf-8")

    block = GateReport(results=[_gate_r_result(
        passed=False,
        evidence={
            "p0_count": 0,
            "delivery": "pass",
            "floor_100": 85.0,
            "dimensions": {k: 8.5 for k in [
                "academic_rigor", "novelty_positioning", "experimental_completeness",
                "writing_quality", "practical_feasibility", "citation_accuracy",
                "format_compliance",
            ]},
            "review_log_present": True,
            "provenance_findings": [
                "review verdict is stale: manuscript changed after the review was written"
            ],
        },
    )])
    assert paper_pipeline._classify_review_heal_engine_defect(tmp_path, block) is None


def test_review_heal_classifier_ignores_non_r_block(tmp_path: Path) -> None:
    block = GateReport(results=[GateResult(
        gate_id="D", passed=False, severity=GateSeverity.BLOCK, details="readability floor"
    )])
    assert paper_pipeline._classify_review_heal_engine_defect(tmp_path, block) is None
