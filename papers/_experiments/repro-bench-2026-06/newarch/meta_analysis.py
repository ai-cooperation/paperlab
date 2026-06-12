#!/usr/bin/env python3
"""Abstract-level meta-analysis lane — answers "is X effective / how large is the
effect" for ANY topic, on real data, CPU-only, deterministically.

Pipeline (no LLM anywhere — mechanical extraction with verbatim evidence):
1. Collect OpenAlex works for the topic (articles with abstracts), reconstruct
   abstracts from the inverted index.
2. Extract quantitative effects with strict regexes: OR/RR/HR + 95% CI,
   standardized mean differences, sample sizes. Every extraction keeps the
   verbatim source sentence (auditable; nothing is paraphrased or invented).
3. Pool ratio measures per type with DerSimonian-Laird random effects
   (log scale, SE from the CI), report I^2 / tau^2; effects without a usable
   CI are listed but never pooled.
4. Emit real_results.json (status=completed, simulated=False, `meta` block)
   mirroring the other lanes so tables/review/floor consume it.

Honesty bounds (stated in the paper's Limitations by the writer prompt):
abstract-level extraction only (no full-text), pattern-based screening — a
rapid evidence synthesis, not a PRISMA full systematic review.

Usage: python3 meta_analysis.py "<topic>" [out_dir] [max_works]
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import synthesis

MAILTO = "aicooperation.tw@gmail.com"
OPENALEX_WORKS = "https://api.openalex.org/works"
UA = f"paperbench/1.0 (mailto:{MAILTO})"
PER_PAGE = 200
MIN_STUDIES_TO_COMPLETE = 3  # fewer extractable studies -> blocked (fail-closed)


def _get(url: str, timeout: int = 45, retries: int = 4) -> dict[str, Any]:
    """OpenAlex fetch with retry+backoff. OpenAlex intermittently 503s / times out
    (especially recovering from an outage); collect() paginates ~10 sequential
    requests, so without retry one transient failure kills the whole run. Retry
    5xx/timeouts with exponential backoff; 4xx is a real error and raises at once."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code < 500:                # 4xx -> client error, do not retry
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = exc
        time.sleep(min(2 ** attempt, 8))      # 1, 2, 4, 8s
    raise last if last else RuntimeError("OpenAlex fetch failed")


def reconstruct_abstract(inv: dict[str, list[int]] | None) -> str:
    if not isinstance(inv, dict) or not inv:
        return ""
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def collect(topic: str, max_works: int = 1200, timeout: int = 30) -> tuple[list[dict[str, Any]], int]:
    """Articles with abstracts for the topic. Returns (works, total_count)."""
    select = "title,doi,publication_year,cited_by_count,abstract_inverted_index"
    flt = "type:article,has_abstract:true"
    cursor = "*"
    works: list[dict[str, Any]] = []
    total = 0
    while cursor and len(works) < max_works:
        q = urllib.parse.urlencode({
            "search": topic, "filter": flt,
            "per-page": min(PER_PAGE, max_works - len(works)),
            "cursor": cursor, "select": select, "mailto": MAILTO,
        })
        body = _get(f"{OPENALEX_WORKS}?{q}", timeout)
        meta = body.get("meta") or {}
        total = int(meta.get("count") or total)
        page = body.get("results") or []
        works.extend(page)
        cursor = meta.get("next_cursor")
        if not page:
            break
        time.sleep(0.1)
    return works, total


def run(topic: str, out_dir: Path, max_works: int = 1200,
        syn_type: str = "intervention", picos_spec: dict[str, Any] | None = None) -> dict[str, Any]:
    started = time.time()
    out_dir = out_dir.expanduser().resolve()
    (out_dir / "real_experiments").mkdir(parents=True, exist_ok=True)

    def finish(result: dict[str, Any]) -> dict[str, Any]:
        (out_dir / "real_experiments" / "real_results.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result

    import corpus_sources
    try:
        works, total, by_source = corpus_sources.collect_corpus(topic, max_works)
    except urllib.error.HTTPError as exc:
        kind = "rate-limit/credit exhausted" if exc.code in (429, 503) else f"HTTP {exc.code}"
        return finish({"status": "blocked", "simulated": False, "source": "corpus",
                       "reason": f"corpus collection failed ({kind}): {exc}", "topic": topic})
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return finish({"status": "blocked", "simulated": False, "source": "corpus",
                       "reason": f"corpus collection failed: {exc}", "topic": topic})

    stype = str(syn_type or "intervention").lower()
    if stype not in synthesis.SYNTHESIS_TYPES:
        stype = "intervention"
    picos = picos_spec or {}
    moderators = [m for m in (picos.get("moderators") or []) if isinstance(m, dict)]

    effects: list[dict[str, Any]] = []
    screened = excluded = 0
    for w in works:
        abstract = w.get("abstract") or reconstruct_abstract(w.get("abstract_inverted_index"))
        if not abstract:
            continue
        screened += 1
        ok, _reason = synthesis.screen_picos((w.get("title") or "") + " " + abstract, picos)
        if not ok:
            excluded += 1
            continue
        effects.extend(synthesis.extract(stype, abstract, w, moderators=moderators))
    studies = {(e["doi"] or e["title"]) for e in effects}

    if len(studies) < MIN_STUDIES_TO_COMPLETE:
        return finish({"status": "blocked", "simulated": False, "source": "OpenAlex",
                       "reason": f"only {len(studies)} eligible studies with extractable "
                                 f"{stype} effects (need >= {MIN_STUDIES_TO_COMPLETE}); not "
                                 "viable for this topic/type at the abstract level",
                       "topic": topic, "synthesis_type": stype,
                       "prisma": {"identified": total, "scanned": len(works),
                                  "with_abstract": screened, "excluded_picos": excluded,
                                  "studies_with_effects": len(studies)}})

    # Pool each scale-homogeneous group (e.g. intervention yields log_ratio + raw;
    # prevalence/correlation a single scale). Pooling de-dupes to one effect/study.
    by_scale: dict[str, list[dict[str, Any]]] = {}
    for e in effects:
        by_scale.setdefault(e.get("scale", "smd"), []).append(e)
    # Raw MD is on heterogeneous original-unit scales -> reported per-study, never
    # pooled (pooling needs a common scale, unverifiable at the abstract level).
    pooled = {scale: p for scale, rows in by_scale.items()
              if scale not in synthesis.NON_POOLABLE_SCALES
              and (p := synthesis.pool(rows, scale)) is not None}
    for p in pooled.values():           # strip internal arrays from the delivered record
        p.pop("_ys", None); p.pop("_ses", None); p.pop("_studies", None)

    # Sensitivity + small-study analyses on the primary (largest) pool — turns the
    # reviewer's "precluded" list into delivered analyses, deterministically.
    sensitivity: dict[str, Any] = {}
    poolable = {s: rows for s, rows in by_scale.items() if s in pooled}
    if poolable:
        primary = max(poolable, key=lambda s: len(poolable[s]))
        prim_pool = synthesis.pool(by_scale[primary], primary)
        if prim_pool:
            eg = synthesis.egger_test(prim_pool)
            if eg:
                sensitivity["egger"] = eg
            loo = synthesis.leave_one_out(by_scale[primary], primary)
            if loo:
                sensitivity["leave_one_out"] = loo
            # Subgroup by each contract-defined moderator (e.g. delivery_mode),
            # falling back to outcome_domain. A level needs >=2 distinct studies.
            keys = [str(m.get("name")) for m in moderators if m.get("name")] or ["outcome_domain"]
            for key in keys:
                sg = synthesis.subgroup(by_scale[primary], primary, key)
                if len(sg) >= 2:
                    sensitivity[f"subgroup_by_{key}"] = sg

    effect_dois = {str(e.get("doi") or "").lower() for e in effects}
    background = sorted(
        (w for w in works if w.get("doi") and str(w["doi"]).lower() not in effect_dois),
        key=lambda w: -(w.get("cited_by_count") or 0))[:30]
    background_works = [{"title": (w.get("title") or "")[:160], "doi": w.get("doi"),
                         "year": w.get("publication_year"),
                         "cited_by": w.get("cited_by_count")} for w in background]

    return finish({
        "status": "completed", "simulated": False, "source": "OpenAlex",
        "source_type": "literature", "lane": "meta_analysis", "synthesis_type": stype,
        "rows": len(works),
        "meta": {
            "topic": topic, "synthesis_type": stype,
            "prisma": {"identified": total, "scanned": len(works),
                       "with_abstract": screened, "excluded_picos": excluded,
                       "studies_with_effects": len(studies), "effects_extracted": len(effects),
                       "by_source": by_source},
            "picos": picos,
            "effects": effects,
            "background_works": background_works,
            "by_measure_counts": {s: len(v) for s, v in by_scale.items()},
            "pooled": pooled,
            "sensitivity": sensitivity,
            "note": ("abstract-level extraction (no full text); pattern-based screening; "
                     "rapid evidence synthesis, not a full PRISMA systematic review"),
        },
        "gpu_used": False, "simulation_markers": 0,
        "wall_seconds": round(time.time() - started, 1),
    })


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "wearable devices health monitoring older adults effectiveness"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    mw = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    r = run(topic, out, mw)
    slim = {k: v for k, v in r.items() if k != "meta"}
    print(json.dumps(slim, indent=2, ensure_ascii=False))
    if r.get("meta"):
        m = r["meta"]
        print("prisma:", m["prisma"])
        print("pooled:", json.dumps(m["pooled"], indent=2))
        for e in m["effects"][:5]:
            print("-", e["measure"], e["effect"], f"[{e['ci_low']},{e['ci_high']}]", "|", e["evidence"][:90])
