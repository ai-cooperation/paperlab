#!/usr/bin/env python3
"""Literature / scientometric analysis lane — real data, any topic, CPU-only.

The universal member-level engine: for ANY research topic, collect REAL
bibliometric data from OpenAlex (no fabrication) and compute descriptive
analytics — publication trend, top venues/authors/concepts, citation
distribution. This is genuine "collect data + analyse" that works for every
field (OpenAlex covers all), unlike the HUPD-specific ML experiment lane.

Output mirrors real_experiments/real_results.json so the same downstream
(tables/figures/review) consumes it: status=completed, simulated=False, plus an
`analysis` block of computed metrics. Nothing here is invented — every number is
derived from the OpenAlex response.

Usage: python3 openalex_analysis.py "<topic>" [out_dir] [max_works]
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

MAILTO = "aicooperation.tw@gmail.com"
OPENALEX_WORKS = "https://api.openalex.org/works"
UA = f"paperbench/1.0 (mailto:{MAILTO})"
PER_PAGE = 200  # OpenAlex max page size


def _get(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def collect(topic: str, max_works: int = 400, timeout: int = 30) -> tuple[list[dict[str, Any]], int]:
    """Cursor-paginate OpenAlex works for the topic (capped). Returns (works, total_count).
    Requests only the fields the analysis needs (keeps payload + CPU light)."""
    select = "publication_year,cited_by_count,primary_location,authorships,concepts,title,doi"
    cursor = "*"
    works: list[dict[str, Any]] = []
    total = 0
    while cursor and len(works) < max_works:
        q = urllib.parse.urlencode({
            "search": topic, "per-page": min(PER_PAGE, max_works - len(works)),
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
        time.sleep(0.1)  # polite
    return works, total


def _top(counter: dict[str, int], n: int) -> list[dict[str, Any]]:
    return [{"name": k, "count": v} for k, v in
            sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def analyze(topic: str, works: list[dict[str, Any]], total_count: int) -> dict[str, Any]:
    """Descriptive scientometrics over the collected works. All values derived."""
    years: dict[str, int] = {}
    venues: dict[str, int] = {}
    authors: dict[str, int] = {}
    concepts: dict[str, int] = {}
    cites: list[int] = []
    top_cited: list[dict[str, Any]] = []

    for w in works:
        y = w.get("publication_year")
        if y:
            years[str(y)] = years.get(str(y), 0) + 1
        loc = (w.get("primary_location") or {}).get("source") or {}
        if loc.get("display_name"):
            venues[loc["display_name"]] = venues.get(loc["display_name"], 0) + 1
        for a in (w.get("authorships") or [])[:5]:
            nm = (a.get("author") or {}).get("display_name")
            if nm:
                authors[nm] = authors.get(nm, 0) + 1
        for c in (w.get("concepts") or []):
            if c.get("display_name") and (c.get("level") or 0) >= 1:
                concepts[c["display_name"]] = concepts.get(c["display_name"], 0) + 1
        cb = int(w.get("cited_by_count") or 0)
        cites.append(cb)
        top_cited.append({"title": (w.get("title") or "")[:160], "cited_by": cb,
                          "year": w.get("publication_year"), "doi": w.get("doi")})

    top_cited.sort(key=lambda x: -x["cited_by"])
    year_keys = sorted(int(y) for y in years)
    # Trend: compound annual growth across the covered span (real counts only).
    cagr = None
    if len(year_keys) >= 2:
        first, last = years[str(year_keys[0])], years[str(year_keys[-1])]
        span = year_keys[-1] - year_keys[0]
        if first > 0 and span > 0:
            cagr = round((last / first) ** (1 / span) - 1, 4)

    return {
        "topic": topic,
        "openalex_total_count": total_count,
        "sample_size": len(works),
        "year_range": [year_keys[0], year_keys[-1]] if year_keys else None,
        "publications_per_year": {str(y): years[str(y)] for y in year_keys},
        "yearly_cagr": cagr,
        "citations": {
            "total": sum(cites),
            "mean": round(statistics.mean(cites), 2) if cites else 0,
            "median": statistics.median(cites) if cites else 0,
            "max": max(cites) if cites else 0,
        },
        "top_venues": _top(venues, 10),
        "top_authors": _top(authors, 10),
        "top_concepts": _top(concepts, 15),
        "most_cited": top_cited[:10],
    }


def run(topic: str, out_dir: Path, max_works: int = 400) -> dict[str, Any]:
    started = time.time()
    out_dir = out_dir.expanduser().resolve()
    (out_dir / "real_experiments").mkdir(parents=True, exist_ok=True)
    try:
        works, total = collect(topic, max_works)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        result = {"status": "blocked", "simulated": False, "source": "OpenAlex",
                  "reason": f"OpenAlex collection failed: {exc}", "topic": topic}
        (out_dir / "real_experiments" / "real_results.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result
    if not works:
        result = {"status": "blocked", "simulated": False, "source": "OpenAlex",
                  "reason": f"no OpenAlex works for topic {topic!r}", "topic": topic}
    else:
        result = {
            "status": "completed", "simulated": False, "source": "OpenAlex",
            "source_type": "literature", "lane": "scientometric",
            "rows": len(works), "analysis": analyze(topic, works, total),
            "gpu_used": False, "simulation_markers": 0,
            "wall_seconds": round(time.time() - started, 1),
        }
    (out_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "community detection citation networks"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
    mw = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    print(json.dumps(run(topic, out, mw), indent=2, ensure_ascii=False)[:3000])
