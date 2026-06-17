"""Phase 5 (ENGINE_BUILD_PLAN): three-stage review + self-heal — where 60->80 lives.

A sub-threshold draft triggers fix-agents BY FAILURE TYPE; the loop stops at
(no-P0 AND floor-not-failed AND score>=80) OR after 3 rounds -> terminal block +
report (NEVER a silent pass). Across rounds the deterministic FLOOR stays flat
(evidence-bound) while the strong-brain review score rises — the signature of real
improvement, not gaming. Strong-brain reviewer + fixers are mocked offline.
"""
from __future__ import annotations

import json

import pytest

from framework import Dossier, MockDispatcher, ReviewOutcome, SelfHealLoop

pytestmark = pytest.mark.unit


def _dossier(tmp_path):
    return Dossier.create(tmp_path, "sh", {"topic": "t", "level": "master"})


# ── success after self-heal: floor flat, score rises, stops when it clears ───
def test_selfheal_converges_floor_flat_score_rises(tmp_path):
    # round 1: score 62, two P0 failure types; round 2: 74, fixed P0 but still < 80;
    # round 3: 83 -> clears. The FLOOR is 56 every round (prose fixes can't move it).
    plan = {
        1: ReviewOutcome(1, 62.0, 2, 56.0, False,
                         {"claim_evidence": ["overclaim X"], "coherence": ["gap Y"]}),
        2: ReviewOutcome(2, 74.0, 0, 56.0, False, {"writing": ["clarity Z"]}),
        3: ReviewOutcome(3, 83.0, 0, 56.0, False, {}),
    }
    disp = MockDispatcher()
    loop = SelfHealLoop(_dossier(tmp_path), disp, lambda d, r: plan[r])
    result = loop.run()

    assert result.status == "passed" and result.rounds == 3
    floors = [o.floor for o in result.history]
    scores = [o.score for o in result.history]
    assert floors == [56.0, 56.0, 56.0]                 # evidence-bound: flat
    assert scores == [62.0, 74.0, 83.0] and scores == sorted(scores)   # rising
    # fix-agents dispatched by failure type in the two failing rounds (2 + 1)
    fixer_tasks = [c for c in disp.calls if c.worker_class == "fixer"]
    assert {c.role for c in fixer_tasks} == {"fix:claim_evidence", "fix:coherence", "fix:writing"}
    assert not loop.dossier.data["status"]["blocked"]


# ── never clears -> terminal block + report after max rounds (no silent pass) ─
def test_selfheal_blocks_after_max_rounds(tmp_path):
    stuck = lambda d, r: ReviewOutcome(r, 70.0, 1, 55.0, False, {"coherence": ["still bad"]})
    d = _dossier(tmp_path)
    result = SelfHealLoop(d, MockDispatcher(), stuck, max_rounds=3).run()

    assert result.status == "blocked" and result.rounds == 3
    assert d.data["status"]["blocked"] is True
    blocked = json.loads((tmp_path / "blocked_review.json").read_text(encoding="utf-8"))
    assert blocked["status"] == "blocked_review" and blocked["rounds"] == 3
    assert (tmp_path / "quality_review_log.md").is_file()


# ── floor is the hard cross-check: high model score cannot pass a failed floor ─
def test_failed_floor_blocks_even_with_high_score(tmp_path):
    # strong brain says 95 but the deterministic floor FAILED -> not a pass.
    gamed = lambda d, r: ReviewOutcome(r, 95.0, 0, 40.0, True, {})
    result = SelfHealLoop(_dossier(tmp_path), MockDispatcher(), gamed, max_rounds=2).run()
    assert result.status == "blocked"            # floor_failed overrides the score
    assert all(not o.passed(80.0) for o in result.history)


# ── a P0 blocks even at/above target score ───────────────────────────────────
def test_p0_blocks_even_above_target(tmp_path):
    p0 = lambda d, r: ReviewOutcome(r, 88.0, 1, 70.0, False, {"claim_evidence": ["P0 overclaim"]})
    result = SelfHealLoop(_dossier(tmp_path), MockDispatcher(), p0, max_rounds=2).run()
    assert result.status == "blocked"
    assert result.history[0].passed(80.0) is False


# ── immediate pass: clean first review, no fixers dispatched ─────────────────
def test_immediate_pass_no_fixers(tmp_path):
    clean = lambda d, r: ReviewOutcome(r, 86.0, 0, 72.0, False, {})
    disp = MockDispatcher()
    result = SelfHealLoop(_dossier(tmp_path), disp, clean).run()
    assert result.status == "passed" and result.rounds == 1
    assert not [c for c in disp.calls if c.worker_class == "fixer"]
