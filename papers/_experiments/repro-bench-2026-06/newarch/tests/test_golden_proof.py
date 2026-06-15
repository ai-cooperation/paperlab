"""Phase 10 (ENGINE_BUILD_PLAN): golden-proof acceptance harness.

Offline: prove the bar-check grades a run against the frozen golden score. The LIVE
proof (full paper-draft bundle via Hermes on ac-2012 reproducing >= the golden score
and passing all gates) is a separate ac-2012 invocation — see the skipped LIVE marker.
"""
from __future__ import annotations

import json

import pytest

import golden_proof

pytestmark = pytest.mark.integration


def test_review_score_of_golden(golden_dir):
    assert golden_proof.review_score(golden_dir) == 57.1   # 7-dim mean *10


def test_golden_meets_its_own_bar(golden_dir):
    proof = golden_proof.prove_against_golden(golden_dir, golden_dir)
    assert proof["passed"] is True
    assert proof["candidate_score"] == proof["golden_bar"] == 57.1


def test_degraded_run_fails_the_bar(tmp_path, golden_dir):
    # a candidate that scored below the golden bar is rejected
    (tmp_path / "final_content_review_deterministic.json").write_text(json.dumps(
        {"scores_7dim": {d: {"score": 3.0} for d in
                         ("novelty", "methodological_rigor", "evidence_validity",
                          "literature_grounding", "result_interpretation",
                          "limitation_honesty", "writing_coherence")}}), encoding="utf-8")
    proof = golden_proof.prove_against_golden(tmp_path, golden_dir)
    assert proof["candidate_score"] == 30.0 and proof["passed"] is False


def test_production_run_requires_no_p0(golden_dir):
    # the golden fixture itself has P0s (no_p0=False) -> a PRODUCTION-grade proof
    # (require_no_p0) rejects it even though it meets its own score bar.
    proof = golden_proof.prove_against_golden(golden_dir, golden_dir, require_no_p0=True)
    assert proof["meets_score"] is True and proof["gate_summary"]["no_p0"] is False
    assert proof["passed"] is False


@pytest.mark.skip(reason="LIVE: requires Hermes + 28-skill bundle + codex auth on "
                  "ac-2012 to produce a fresh run; offline harness above grades it.")
def test_golden_paper_on_hermes_LIVE():  # pragma: no cover
    # On ac-2012: run paper_orchestrator over the frozen corpus via Hermes (codex
    # brain + big-pickle), then:
    #   proof = golden_proof.prove_against_golden(fresh_run, golden, require_no_p0=True)
    #   assert proof["passed"] and proof["candidate_score"] >= 75
    ...
