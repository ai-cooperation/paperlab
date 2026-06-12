#!/usr/bin/env python3
"""Multi-source corpus collection for the meta-analysis lane.

OpenAlex was the single corpus source — a single point of failure AND, since its
2026 move to a paid $1/day credit model, a single point of cost. Most meta-
analyses are medical (mindfulness, anxiety, exercise, ...), and Europe PMC is a
better fit there anyway: free, no key, no per-request cost, biomedical-focused,
indexes clinical trials, and returns abstracts directly.

Strategy: Europe PMC FIRST (free); fall back to OpenAlex only when Europe PMC is
thin (a non-medical topic), so paid OpenAlex usage is minimised. Every source
normalises to the same work shape: {title, doi, publication_year,
cited_by_count, abstract, source}. The abstract is plain text (Europe PMC HTML
stripped; OpenAlex inverted index reconstructed) so the extractor is source-blind.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

MAILTO = "aicooperation.tw@gmail.com"
UA = f"paperbench/1.0 (mailto:{MAILTO})"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
OPENALEX = "https://api.openalex.org/works"
_HTML = re.compile(r"<[^>]+>")


def _get(url: str, timeout: int = 45, retries: int = 4) -> dict[str, Any]:
    """HTTP GET with retry+backoff on 5xx/timeout (4xx raises immediately)."""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code < 500:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = exc
        time.sleep(min(2 ** attempt, 8))
    raise last if last else RuntimeError("fetch failed")


def _strip_html(s: str | None) -> str:
    if not s:
        return ""
    return _HTML.sub(" ", s).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def _year(v: Any) -> int | None:
    s = str(v or "")
    return int(s[:4]) if s[:4].isdigit() else None


def collect_europepmc(topic: str, max_works: int = 1500, timeout: int = 45) -> tuple[list[dict[str, Any]], int]:
    """Europe PMC: free, biomedical, abstracts direct. cursorMark pagination."""
    cursor = "*"
    works: list[dict[str, Any]] = []
    total = 0
    while cursor and len(works) < max_works:
        q = urllib.parse.urlencode({
            "query": f"({topic}) AND (HAS_ABSTRACT:Y)", "format": "json",
            "resultType": "core", "pageSize": min(1000, max_works - len(works)),
            "cursorMark": cursor,
        })
        body = _get(f"{EUROPEPMC}?{q}", timeout)
        total = int(body.get("hitCount") or total)
        results = ((body.get("resultList") or {}).get("result")) or []
        for r in results:
            abstract = _strip_html(r.get("abstractText"))
            if not abstract:
                continue
            doi = r.get("doi")
            works.append({
                "title": (r.get("title") or "").rstrip("."), "doi": doi,
                "publication_year": _year(r.get("pubYear")),
                "cited_by_count": r.get("citedByCount") or 0,
                "abstract": abstract, "source": "europepmc",
            })
        nxt = body.get("nextCursorMark")
        if not results or nxt == cursor:
            break
        cursor = nxt
        time.sleep(0.1)
    return works, total


def _reconstruct(inv: dict[str, list[int]] | None) -> str:
    if not isinstance(inv, dict) or not inv:
        return ""
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def collect_openalex(topic: str, max_works: int = 1500, timeout: int = 45) -> tuple[list[dict[str, Any]], int]:
    """OpenAlex (general fallback; PAID since 2026 — use sparingly). Inverted
    index reconstructed to plain abstract."""
    select = "title,doi,publication_year,cited_by_count,abstract_inverted_index"
    cursor = "*"
    works: list[dict[str, Any]] = []
    total = 0
    while cursor and len(works) < max_works:
        q = urllib.parse.urlencode({
            "search": topic, "filter": "type:article,has_abstract:true",
            "per-page": min(200, max_works - len(works)), "cursor": cursor,
            "select": select, "mailto": MAILTO,
        })
        body = _get(f"{OPENALEX}?{q}", timeout)
        meta = body.get("meta") or {}
        total = int(meta.get("count") or total)
        page = body.get("results") or []
        for w in page:
            abstract = _reconstruct(w.get("abstract_inverted_index"))
            if not abstract:
                continue
            works.append({
                "title": w.get("title"), "doi": w.get("doi"),
                "publication_year": w.get("publication_year"),
                "cited_by_count": w.get("cited_by_count") or 0,
                "abstract": abstract, "source": "openalex",
            })
        cursor = meta.get("next_cursor")
        if not page:
            break
        time.sleep(0.1)
    return works, total


def collect_corpus(topic: str, max_works: int = 1500,
                   allow_openalex: bool = True) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    """Europe PMC first (free); supplement with OpenAlex only when Europe PMC is
    thin (likely a non-medical topic). Dedupe by DOI. Returns (works, total, by_source)."""
    works, total = collect_europepmc(topic, max_works)
    by_source = {"europepmc": len(works)}
    if allow_openalex and len(works) < max_works // 2:
        seen = {str(w.get("doi") or "").lower() for w in works if w.get("doi")}
        try:
            oa, oa_total = collect_openalex(topic, max_works - len(works))
        except Exception:  # noqa: BLE001 - OpenAlex paid/flaky; never let it sink a free EPMC run
            oa, oa_total = [], 0
        added = 0
        for w in oa:
            d = str(w.get("doi") or "").lower()
            if d and d in seen:
                continue
            if d:
                seen.add(d)
            works.append(w)
            added += 1
        by_source["openalex"] = added
        total = max(total, oa_total)
    return works, total, by_source


if __name__ == "__main__":
    import sys
    w, t, src = collect_corpus(sys.argv[1] if len(sys.argv) > 1 else "mindfulness anxiety", 200)
    print(f"total~{t} | collected {len(w)} | by_source {src}")
    for x in w[:3]:
        print(" -", x["source"], "|", (x["title"] or "")[:50], "|", (x["abstract"] or "")[:60])
