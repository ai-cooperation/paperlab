"""Phase 6 (ENGINE_BUILD_PLAN): viability probe + tier interaction (§5.1, §5.2).

Over the REAL frozen corpora + contracts: the thin mindfulness corpus is non-viable
(max poolable-k=6 < the credible bar 8); exercise is viable (k=8). On non-viable,
level=master AUTO-PIVOTS + writes a research_steering_log; level=phd PAUSES for the
user (no auto-run). The contract-hash lock travels with every verdict.
"""
from __future__ import annotations

import json

import pytest

from framework import Dossier, ViabilityDecision, contract_hash, handle_viability
from packs.paper import PaperPack

pytestmark = pytest.mark.unit


def _dossier(tmp_path):
    return Dossier.create(tmp_path, "via", {"topic": "t"})


# ── master: non-viable -> autonomous pivot + steering log ────────────────────
def test_mindfulness_master_auto_pivots_with_steering_log(tmp_path, load_fixture_json):
    contract = load_fixture_json("contract_mindfulness.json")   # level=master
    corpus = load_fixture_json("corpus_mindfulness_thin.json")
    d = _dossier(tmp_path)

    dec = handle_viability(PaperPack(), contract, {"corpus": corpus}, d)

    assert isinstance(dec, ViabilityDecision)
    assert dec.verdict.viable is False                          # k=6 < 8
    assert dec.verdict.metric["max_poolable_k"] == 6
    assert dec.status == "auto_pivot" and dec.can_proceed
    assert dec.applied_pivot and dec.applied_pivot in dec.verdict.candidate_pivots
    # research_steering_log written (the sole safeguard for the auto-pivot)
    log = (tmp_path / "research_steering_log.md").read_text(encoding="utf-8")
    assert "discovery" in log and "why pivoted" in log
    assert dec.steering_log["discarded"]                       # transparent: what was dropped
    assert dec.verdict.contract_hash == contract_hash(contract)
    assert d.data["status"]["blocked"] is False               # master proceeds
    assert d.data["pack_ext"]["research_steering_log"]["why_pivoted"]
    # the auto-pivot ACTUALLY mutates the contract (codex: was logged-only) + re-hashes
    assert d.data["contract"]["value_framing"] == "direction_and_uncertainty"
    assert contract_hash(d.data["contract"]) != dec.verdict.contract_hash
    assert d.data["pack_ext"]["research_steering_log"]["contract_hash_after"]


# ── phd: non-viable -> paused_for_user, NO auto-run ──────────────────────────
def test_mindfulness_phd_pauses_for_user(tmp_path, load_fixture_json):
    contract = dict(load_fixture_json("contract_mindfulness.json"))
    contract["level"] = "phd"
    corpus = load_fixture_json("corpus_mindfulness_thin.json")
    d = _dossier(tmp_path)

    dec = handle_viability(PaperPack(), contract, {"corpus": corpus}, d)

    assert dec.status == "paused_for_user" and not dec.can_proceed
    assert dec.applied_pivot is None                           # no autonomous pivot
    assert not (tmp_path / "research_steering_log.md").exists()
    assert d.data["status"]["phase"] == "paused_for_user"
    assert d.data["status"]["blocked"] is True
    pc = d.data["pending_confirmation"]
    assert pc["pivot_options"] and pc["contract_hash"] == contract_hash(contract)


# ── viable topic proceeds with no pivot, no pause ────────────────────────────
def test_exercise_viable_proceeds(tmp_path, load_fixture_json):
    contract = load_fixture_json("contract_paper.json")        # exercise
    corpus = load_fixture_json("corpus_exercise.json")
    d = _dossier(tmp_path)

    dec = handle_viability(PaperPack(), contract, {"corpus": corpus}, d)
    assert dec.status == "viable" and dec.can_proceed
    assert dec.verdict.viable is True and dec.verdict.metric["max_poolable_k"] == 8
    assert d.data["status"]["blocked"] is False
    assert "pending_confirmation" not in d.data


# ── the verdict is recorded in the dossier (projection / status feed) ────────
def test_viability_recorded_in_dossier(tmp_path, load_fixture_json):
    contract = load_fixture_json("contract_mindfulness.json")
    corpus = load_fixture_json("corpus_mindfulness_thin.json")
    d = _dossier(tmp_path)
    handle_viability(PaperPack(), contract, {"corpus": corpus}, d)
    reloaded = json.loads((tmp_path / "dossier.json").read_text(encoding="utf-8"))
    v = reloaded["viability"]
    assert v["viable"] is False and v["metric"]["max_poolable_k"] == 6
    assert v["candidate_pivots"]
