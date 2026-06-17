"""Integration step 2 (BSIDE_WEB_INTEGRATION_PLAN §3b): the a-side viability service —
collect/cache by contract_hash, run handle_viability, and seed the cache into a run
dir so the submit reuses it. Collector is injected so tests never hit the network.
"""
from __future__ import annotations

import pytest

import viability_service
from framework import contract_hash

pytestmark = pytest.mark.unit


def _mock_collector(corpus):
    works = corpus["works"]

    def collect(query, max_works):
        return works[:max_works], corpus.get("total", len(works)), corpus.get("by_source", {})

    return collect


def test_collect_cached_caches_by_contract_hash(tmp_path, load_fixture_json):
    corpus = load_fixture_json("corpus_exercise.json")
    contract = load_fixture_json("contract_paper.json")
    _, h1, cached1 = viability_service.collect_cached(tmp_path, contract, collector=_mock_collector(corpus))
    assert cached1 is False and h1 == contract_hash(contract)

    calls = {"n": 0}

    def coll2(q, m):
        calls["n"] += 1
        return [], 0, {}

    _, h2, cached2 = viability_service.collect_cached(tmp_path, contract, collector=coll2)
    assert cached2 is True and calls["n"] == 0 and h2 == h1     # cache hit, no re-collect


def test_probe_returns_verdict_and_authoritative_hash(tmp_path, load_fixture_json):
    corpus = load_fixture_json("corpus_exercise.json")
    contract = load_fixture_json("contract_paper.json")
    out = viability_service.probe(tmp_path, contract, collector=_mock_collector(corpus))
    assert out["viable"] is True and out["contract_hash"] == contract_hash(contract)
    assert out["metric"]["max_poolable_k"] == 8 and out["corpus_cached"] is False
    assert (tmp_path / "_viability_cache" / out["contract_hash"] / "viability.json").is_file()


def test_submit_reuses_cached_corpus(tmp_path, load_fixture_json):
    corpus = load_fixture_json("corpus_exercise.json")
    contract = load_fixture_json("contract_paper.json")
    viability_service.collect_cached(tmp_path, contract, collector=_mock_collector(corpus))
    run = tmp_path / "run"
    run.mkdir()
    assert viability_service.seed_run_corpus(tmp_path, contract, run) is True
    assert (run / "_corpus_cache.json").is_file()              # data phase will reuse it


def test_seed_misses_cleanly_without_cache(tmp_path, load_fixture_json):
    run = tmp_path / "run"
    run.mkdir()
    assert viability_service.seed_run_corpus(tmp_path, load_fixture_json("contract_paper.json"), run) is False
