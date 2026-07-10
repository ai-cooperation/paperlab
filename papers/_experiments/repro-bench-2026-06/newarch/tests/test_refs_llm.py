"""LLM-seeded, CrossRef-verified reference discovery — offline (mocked CrossRef).

The guarantee under test: a candidate enters the bibliography ONLY if CrossRef returns
a real paper whose title matches, and the kept metadata is CrossRef's (not the LLM's).
A hallucinated candidate (no CrossRef match) is dropped. (The live CrossRef path is
smoke-proven separately on ac-2012.)
"""
from __future__ import annotations

import json
from pathlib import Path

import dataset_lane.refs_llm as R


# a tiny fake CrossRef index keyed by a distinctive query term
_FAKE = {
    "renewable": [{"DOI": "10.1016/j.enpol.2009.09.002",
                   "title": ["Renewable energy consumption and economic growth: evidence from OECD"],
                   "author": [{"family": "Apergis"}, {"family": "Payne"}],
                   "published": {"date-parts": [[2010]]}, "is-referenced-by-count": 900}],
    "threshold": [{"DOI": "10.1016/j.eneco.2017.01.004",
                   "title": ["A dynamic panel threshold model of growth and emissions"],
                   "author": [{"family": "Aye"}, {"family": "Edoja"}],
                   "published": {"date-parts": [[2017]]}}],
}


def _fake_search(query, rows=4, timeout=20):
    q = query.lower()
    for term, items in _FAKE.items():
        if term in q:
            return items
    return []   # nothing matches a hallucinated title


def test_title_match():
    assert R.title_match("Renewable energy consumption and economic growth",
                         "Renewable energy consumption and economic growth: evidence from OECD")
    assert not R.title_match("Renewable energy and growth", "Deep learning for protein folding")
    assert not R.title_match("the of a", "the of a and")          # too few significant tokens


def test_verify_keeps_real_drops_hallucinated(monkeypatch):
    monkeypatch.setattr(R, "crossref_search", _fake_search)
    cands = [
        {"title": "Renewable energy consumption and economic growth", "author": "Apergis", "year": 2010},
        {"title": "A dynamic panel threshold model of growth and emissions", "author": "Aye", "year": 2017},
        {"title": "Quantum entanglement of renewable portfolios in GDP manifolds", "author": "Nobody", "year": 2021},
    ]
    kept = R.verify_candidates(cands, pause=0.0)
    dois = {k["doi"] for k in kept}
    assert "10.1016/j.enpol.2009.09.002" in dois        # real -> kept
    assert "10.1016/j.eneco.2017.01.004" in dois         # real -> kept
    assert len(kept) == 2                                 # hallucinated -> dropped


def test_verify_rejects_wrong_author(monkeypatch):
    """A real DOI whose title token-matches but whose AUTHORS differ is the dangerous
    'real DOI on the wrong paper' case (agy finding) — it must be dropped."""
    monkeypatch.setattr(R, "crossref_search", _fake_search)
    cand = {"title": "Renewable energy consumption and economic growth",
            "author": "Wrongperson", "year": 2010}
    assert R.verify_candidate(cand) is None        # title matched but author did not


def test_verify_uses_crossref_metadata_not_llm(monkeypatch):
    """The LLM's claimed DOI/year are discarded; CrossRef's canonical values are kept."""
    monkeypatch.setattr(R, "crossref_search", _fake_search)
    cand = {"title": "Renewable energy consumption and economic growth",
            "author": "Apergis", "year": 1999, "doi": "10.9999/fabricated-by-llm"}
    m = R.verify_candidate(cand)
    assert m["doi"] == "10.1016/j.enpol.2009.09.002"     # CrossRef DOI, not the LLM's
    assert m["year"] == 2010                              # CrossRef year, not the LLM's 1999


def test_verify_dedup_across_seen(monkeypatch):
    monkeypatch.setattr(R, "crossref_search", _fake_search)
    seen = {"10.1016/j.enpol.2009.09.002"}               # already collected
    kept = R.verify_candidates(
        [{"title": "Renewable energy consumption and economic growth", "author": "Apergis"}],
        pause=0.0, seen=seen)
    assert kept == []                                     # not double-counted


def test_collect_loops_until_target(monkeypatch, tmp_path):
    monkeypatch.setattr(R, "crossref_search", _fake_search)
    (tmp_path / "real_experiments").mkdir(parents=True)
    calls = {"n": 0}

    def fake_brain(prompt, writes):
        calls["n"] += 1
        # round 1 proposes the renewable paper; round 2 proposes the threshold paper
        cand = ({"title": "Renewable energy consumption and economic growth", "author": "Apergis"}
                if calls["n"] == 1 else
                {"title": "A dynamic panel threshold model of growth and emissions", "author": "Aye"})
        (tmp_path / R.CANDIDATES_FILE).write_text(json.dumps({"candidates": [cand]}), encoding="utf-8")
        return True

    res = R.collect(tmp_path, "renewable energy growth panel", fake_brain,
                    target=2, max_rounds=4, pause=0.0)
    assert res["verified"] == 2 and res["rounds"] == 2    # stopped as soon as target met


def test_collect_seeds_count(monkeypatch, tmp_path):
    """Seed DOIs (e.g. the OpenAlex corpus) pre-load the count before any LLM round."""
    monkeypatch.setattr(R, "crossref_search", lambda *a, **k: [])
    (tmp_path / "real_experiments").mkdir(parents=True)
    seed = [{"doi": "10.1/a", "title": "A"}, {"doi": "10.2/b", "title": "B"}]

    def brain(prompt, writes):
        (tmp_path / R.CANDIDATES_FILE).write_text('{"candidates": []}', encoding="utf-8")
        return True

    res = R.collect(tmp_path, "topic", brain, target=2, seed_dois=seed, pause=0.0)
    assert res["verified"] == 2                            # met by seeds alone, no LLM rounds needed
