"""Phase 8 (ENGINE_BUILD_PLAN): viability-lock + deterministic contract derivation.

The canonical a-side rules the b-side Worker wraps: submit refuses without an approved
hash-matched viability-lock; the contract is derived from STRUCTURED grill answers
(not chat prose); a scope change after approval invalidates the lock -> re-probe.
"""
from __future__ import annotations

import pytest

from framework import (
    derive_contract,
    lock_for,
    submit_gate,
)
from packs.paper import PaperPack

pytestmark = pytest.mark.unit

GRILL = {
    "job_id": "p1", "source": "paper-mcp", "level": "master",
    "topic": "Exercise and depression in older adults",
    "research_question": "Do exercise interventions reduce depressive symptoms?",
    "contribution": "abstract-level pooled estimate",
    "data_source": {"type": "meta-analysis", "name": "exercise depression older adults"},
    "synthesis": {"type": "intervention",
                  "picos": {"require_all": [["exercise"], ["depression"]],
                            "require_any": ["randomized"], "exclude_terms": []}},
}


def test_contract_derived_deterministically_from_grill():
    pack = PaperPack()
    c1 = derive_contract(pack, GRILL)
    c2 = derive_contract(pack, dict(GRILL))
    assert c1["contract_hash"] == c2["contract_hash"]        # deterministic
    assert c1["synthesis"]["picos"]                          # structured, not prose


def test_submit_refused_without_lock():
    c = derive_contract(PaperPack(), GRILL)
    d = submit_gate(c, None)
    assert d.allowed is False and "no viability-lock" in d.reason


def test_submit_refused_when_lock_not_approved():
    c = derive_contract(PaperPack(), GRILL)
    lock = lock_for(c, approved=False, verdict_viable=True)
    assert submit_gate(c, lock).allowed is False


def test_submit_allowed_with_approved_matched_viable_lock():
    c = derive_contract(PaperPack(), GRILL)
    lock = lock_for(c, approved=True, verdict_viable=True)
    d = submit_gate(c, lock)
    assert d.allowed is True


def test_scope_change_after_approval_requires_reprobe():
    pack = PaperPack()
    c = derive_contract(pack, GRILL)
    lock = lock_for(c, approved=True, verdict_viable=True)         # approved for THIS scope
    changed = dict(GRILL)
    changed["synthesis"] = {**GRILL["synthesis"],
                            "picos": {**GRILL["synthesis"]["picos"],
                                      "require_all": [["exercise"], ["anxiety"]]}}  # PICOS changed
    c2 = derive_contract(pack, changed)
    d = submit_gate(c2, lock)
    assert d.allowed is False and d.needs_reprobe is True          # hash mismatch -> re-probe


def test_non_viable_approved_lock_still_refused():
    c = derive_contract(PaperPack(), GRILL)
    lock = lock_for(c, approved=True, verdict_viable=False)
    assert submit_gate(c, lock).allowed is False
