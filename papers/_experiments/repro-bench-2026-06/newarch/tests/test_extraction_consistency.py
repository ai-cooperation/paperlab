"""Phase 1 (BLOCKING): kill the poolable-k divergence (probe=8 / lane=3 / direct=23).

Root cause (confirmed over the frozen corpus): poolable-k is PER SCALE, counted
after pool()'s one-effect-per-study dedup. SMD k=8 and log_ratio k=3 are different
strata (the "8 vs 3" was comparing two scales). The "23"/64 was a naive raw-effect
count (mixed scales, multi-effect studies, non-poolable MD) — never a poolable-k.

GREEN: one authoritative `synthesis.poolable_k_by_scale`; the lane, the phase0
probe, and pack viability all agree with it over the same (corpus, picos).
"""
from __future__ import annotations

import json

import pytest

import meta_analysis
import phase0_calibration
import synthesis
from packs.paper import PaperPack

pytestmark = [pytest.mark.integration]

EXPECTED_K = {"smd": 8, "log_ratio": 3}   # the golden exercise-depression run


@pytest.fixture
def corpus_run_dir(tmp_path, load_fixture_json):
    """A run dir seeded with the frozen exercise corpus as `_corpus_cache.json`
    (the lane + probe read this; no network)."""
    corpus = load_fixture_json("corpus_exercise.json")
    cache = tmp_path / "_corpus_cache.json"
    cache.write_text(json.dumps(corpus), encoding="utf-8")
    return tmp_path, corpus


def _picos():
    contract = json.loads((
        __import__("pathlib").Path(__file__).resolve().parent
        / "fixtures" / "contract_paper.json").read_text(encoding="utf-8"))
    return contract["synthesis"]["picos"]


def test_authoritative_poolable_k_by_scale(load_fixture_json):
    corpus = load_fixture_json("corpus_exercise.json")
    k = synthesis.poolable_k_by_scale(corpus["works"], _picos(), "intervention")
    assert k == EXPECTED_K


def test_lane_agrees_with_authoritative(corpus_run_dir):
    run_dir, corpus = corpus_run_dir
    r = meta_analysis.run(corpus["query"], run_dir, max_works=corpus["max_works"],
                          syn_type="intervention", picos_spec=_picos(),
                          cache_path=run_dir / "_corpus_cache.json")
    assert r["status"] == "completed"
    lane_k = {s: p["k"] for s, p in (r["meta"]["pooled"]).items()}
    assert lane_k == EXPECTED_K
    assert lane_k == synthesis.poolable_k_by_scale(corpus["works"], _picos(), "intervention")


def test_phase0_probe_agrees_with_authoritative(corpus_run_dir):
    run_dir, corpus = corpus_run_dir
    probe = phase0_calibration.feasibility_probe(
        run_dir, corpus["query"], "intervention", _picos())
    assert probe["status"] == "completed"
    assert probe["poolable_k"] == EXPECTED_K
    assert probe["max_poolable_k"] == max(EXPECTED_K.values())   # 8 (max across scales)


def test_pack_viability_agrees_with_authoritative(load_fixture_json):
    corpus = load_fixture_json("corpus_exercise.json")
    contract = load_fixture_json("contract_paper.json")
    v = PaperPack().viability_probe(contract, {"corpus": corpus})
    assert v.metric["poolable_k"] == EXPECTED_K
    assert v.metric["max_poolable_k"] == 8


def test_naive_count_is_not_poolable_k(load_fixture_json):
    """Document the trap: raw effect count >> poolable-k (the source of the '23')."""
    corpus = load_fixture_json("corpus_exercise.json")
    by_scale = synthesis.collect_effects_by_scale(corpus["works"], _picos(), "intervention")
    raw = sum(len(v) for v in by_scale.values())
    pooled_total = sum(EXPECTED_K.values())     # 11
    assert raw > pooled_total                    # 64 raw > 11 pooled — never conflate
    assert "md" in by_scale                       # raw MD inflates the naive count
    assert "md" not in synthesis.poolable_k_by_scale(corpus["works"], _picos(), "intervention")
