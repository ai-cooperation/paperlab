"""a-side viability probe service (BSIDE_WEB_INTEGRATION_PLAN §3b, codex review 2026-06-16).

The probe is NOT cheap — `handle_viability` needs a real corpus (poolable-k over works).
So: collect ONCE per scope, cache by `contract_hash`; the grill probe, the submit
re-probe, and `run_paper`'s data phase all REUSE the cached corpus (at most one
OpenAlex collect per scope). The a-side is authoritative for `contract_hash` (the
b-side stores it, never recomputes it).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import corpus_sources
import paper_driver
from framework import Dossier, contract_hash, handle_viability
from packs.insurance import InsurancePack
from packs.paper import PaperPack

VIABILITY_CACHE = "_viability_cache"
DEFAULT_MAX_WORKS = 2400


def _pack_for(contract: dict[str, Any]):
    return InsurancePack() if "insurance" in str(contract.get("source") or "").lower() else PaperPack()


def _cache_dir(jobs_dir: Path, h: str) -> Path:
    return Path(jobs_dir) / VIABILITY_CACHE / h


def corpus_cache_path(jobs_dir: Path, h: str) -> Path:
    return _cache_dir(jobs_dir, h) / "_corpus_cache.json"


def collect_cached(jobs_dir: Path, contract: dict[str, Any], *,
                   max_works: int = DEFAULT_MAX_WORKS,
                   collector=corpus_sources.collect_corpus) -> tuple[dict[str, Any], str, bool]:
    """Return (corpus, contract_hash, was_cached). Collects via the SAME query the
    meta lane uses (`_literature_query`) + caches in the lane's cache format so
    `meta_analysis.run` reuses it (query + max_works must match to hit the cache)."""
    h = contract_hash(contract)
    cache = corpus_cache_path(jobs_dir, h)
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8")), h, True
    query = paper_driver._literature_query(contract)
    works, total, by_source = collector(query, max_works)
    corpus = {"query": query, "max_works": max_works, "works": works,
              "total": total, "by_source": by_source}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    return corpus, h, False


def probe(jobs_dir: Path, contract: dict[str, Any], *,
          collector=corpus_sources.collect_corpus) -> dict[str, Any]:
    """Run the viability probe (collect/cache + handle_viability) and return the
    lockable verdict + the a-side-authoritative contract_hash."""
    pack = _pack_for(contract)
    cached = False
    if pack.name == "paper":
        corpus, h, cached = collect_cached(jobs_dir, contract, collector=collector)
        sources: dict[str, Any] = {"corpus": corpus}
    else:                                            # insurance: KB dir from the contract
        h = contract_hash(contract)
        sources = {"kb_dir": (contract.get("data_source") or {}).get("kb_dir")}
    d = Dossier.create(_cache_dir(jobs_dir, h), str(contract.get("job_id") or h), contract, mode=pack.name)
    decision = handle_viability(pack, contract, sources, d)
    v = decision.verdict
    out = {
        "contract_hash": h, "viable": v.viable, "reason": v.reason, "metric": v.metric,
        "candidate_pivots": v.candidate_pivots, "tier_verdicts": v.tier_verdicts,
        "decision": decision.status, "applied_pivot": decision.applied_pivot,
        "pivoted_contract": (d.data.get("contract") if decision.status == "auto_pivot" else None),
        "corpus_cached": cached,
    }
    (_cache_dir(jobs_dir, h) / "viability.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def seed_run_corpus(jobs_dir: Path, contract: dict[str, Any], run_dir: Path) -> bool:
    """Copy the cached corpus into run_dir before run_paper so the data phase reuses
    it (no second OpenAlex collect). True if a cache was found."""
    cache = corpus_cache_path(jobs_dir, contract_hash(contract))
    if cache.is_file():
        shutil.copy(cache, Path(run_dir) / "_corpus_cache.json")
        return True
    return False
