#!/usr/bin/env python3
"""LLM-seeded, CrossRef-verified reference discovery for the dataset lane.

WHY: the dataset lane built its related-work bibliography from OpenAlex ALONE
(single source, capped), so it shipped ~14 refs — below the paper-draft skill's
HARD >=35. Semantic Scholar (the skill's other source) is rate-limited and errors
out, so hammering its API is a dead end.

STRATEGY (the user's design): let the BRAIN (codex) GENERATE a candidate reading
list for the topic — LLMs carry broad, real knowledge of a field's literature —
then VERIFY every candidate against CrossRef and keep only the ones that really
exist. The LLM does DISCOVERY; CrossRef does the REALITY CHECK.

ANTI-HALLUCINATION (the iron rule — "嚴禁 AI 假引用"): a candidate is a SEARCH
SEED, never a fact. We search CrossRef by the candidate's TITLE (+author), accept
it ONLY if CrossRef returns a real paper whose title token-matches, and we keep
CrossRef's CANONICAL metadata (real DOI/authors/year) — the LLM's claimed DOI is
discarded. A hallucinated paper has no CrossRef match and is dropped automatically.
So nothing enters the bibliography that CrossRef has not confirmed to exist.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CANDIDATES_FILE = "real_experiments/ref_candidates.json"
MAILTO = "aicooperation.tw@gmail.com"
_UA = f"paperbench/1.0 (mailto:{MAILTO})"
_CROSSREF = "https://api.crossref.org/works"

# Generic academic jargon is NOT distinctive — a title made of these can coincidentally
# overlap an unrelated paper. Strip them so the match rests on the topical content words.
_STOP = {"the", "a", "an", "of", "and", "or", "for", "to", "in", "on", "with", "from",
         "by", "as", "at", "is", "are", "using", "based", "via", "study", "analysis",
         "approach", "toward", "towards", "case", "evidence", "new", "novel",
         "empirical", "investigation", "review", "relationship", "role", "impact",
         "impacts", "effect", "effects", "assessment", "dynamics", "nexus", "determinants",
         "evaluation", "examining", "exploring", "comparative", "perspective", "perspectives"}
# A match needs to clear a HIGH bar: a real DOI on the wrong paper is worse than a miss.
_TITLE_THRESHOLD = 0.8


def _title_tokens(title: str) -> set[str]:
    """Significant lowercase word-tokens of a title (>=3 letters, minus stopwords)."""
    return {w for w in re.findall(r"[a-z0-9]{3,}", str(title or "").lower()) if w not in _STOP}


def title_match(candidate: str, found: str, threshold: float = _TITLE_THRESHOLD) -> bool:
    """True when the FOUND paper's title covers most of the CANDIDATE's significant
    words — the candidate really is this paper, not a coincidental search hit."""
    ct, ft = _title_tokens(candidate), _title_tokens(found)
    if len(ct) < 2:
        return False
    return len(ct & ft) / len(ct) >= threshold


def _surname(author: str) -> str:
    """The surname token from a candidate author string ('Apergis' or 'N. Apergis')."""
    toks = re.findall(r"[A-Za-z][A-Za-z'\-]{1,}", str(author or ""))
    return (toks[-1] if toks else "").lower()


def _author_match(candidate_author: str, item: dict[str, Any]) -> bool:
    """The candidate's author surname must appear among CrossRef's author family names.
    Empty candidate author -> no author signal, fall back to the (stricter) title check."""
    want = _surname(candidate_author)
    if not want:
        return True
    families = {str(a.get("family") or "").lower() for a in (item.get("author") or [])}
    return any(want == f or want in f or f in want for f in families if f)


def crossref_search(query: str, rows: int = 4, timeout: int = 20) -> list[dict[str, Any]]:
    """CrossRef bibliographic search (title/free-text). Returns raw items (real DOIs).
    Errors return [] — a flaky single query must never sink the whole collection."""
    params = {"query.bibliographic": query, "rows": str(rows),
              "filter": "type:journal-article", "mailto": MAILTO,
              "select": "DOI,title,author,published,container-title,is-referenced-by-count"}
    url = f"{_CROSSREF}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode("utf-8", "ignore"))
        return payload.get("message", {}).get("items", [])
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError, ValueError):
        return []


def _item_year(item: dict[str, Any]) -> int | None:
    parts = ((item.get("published") or {}).get("date-parts") or [[None]])
    try:
        return int(parts[0][0])
    except (TypeError, ValueError, IndexError):
        return None


def verify_candidate(cand: dict[str, Any], *, pause: float = 0.0,
                     topic_terms: set[str] | None = None) -> dict[str, Any] | None:
    """Search CrossRef for ONE LLM candidate and return the real matched item (with
    canonical DOI/title/year) or None. The LLM's own DOI is NOT used — only its title
    (+ first author) seed the search, and the result must token-match the title AND author.
    If `topic_terms` is given, the matched paper must also be ON-TOPIC (its title shares a
    distinctive topic word) — so a real DOI on a coincidentally title-overlapping paper
    from a DIFFERENT FIELD is rejected, not just a different-author one."""
    title = str(cand.get("title") or "").strip()
    if len(_title_tokens(title)) < 2:
        return None
    author = str(cand.get("author") or cand.get("first_author") or "").strip()
    query = f"{title} {author}".strip()
    items = crossref_search(query)
    if pause:
        time.sleep(pause)
    for item in items:
        found_title = (item.get("title") or [""])[0]
        doi = str(item.get("DOI") or "").strip().lower()
        # title AND author AND topic must match: a real DOI on a coincidentally overlapping
        # but WRONG paper (different authors OR a different field) is rejected.
        if not (doi and found_title and title_match(title, found_title) and _author_match(author, item)):
            continue
        if topic_terms and not (_title_tokens(found_title) & topic_terms):
            continue                                  # real paper, wrong field -> drop
        return {"doi": doi, "title": found_title, "year": _item_year(item),
                "is_referenced_by_count": item.get("is-referenced-by-count")}
    return None


def verify_candidates(candidates: list[dict[str, Any]], *, pause: float = 0.34,
                      seen: set[str] | None = None,
                      topic_terms: set[str] | None = None) -> list[dict[str, Any]]:
    """Verify a list of LLM candidates against CrossRef; return the de-duplicated real
    matches. `pause` keeps under CrossRef's polite-pool rate; `seen` carries DOIs across
    rounds so a re-suggested paper is not double-counted; `topic_terms` rejects on-title
    but off-FIELD matches."""
    seen = seen if seen is not None else set()
    kept: list[dict[str, Any]] = []
    for cand in candidates:
        match = verify_candidate(cand, pause=pause, topic_terms=topic_terms)
        if match and match["doi"] not in seen:
            seen.add(match["doi"])
            kept.append(match)
    return kept


def _read_candidates(run_dir: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads((Path(run_dir) / CANDIDATES_FILE).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        data = data.get("candidates") or data.get("references") or []
    return [c for c in data if isinstance(c, dict) and c.get("title")]


def _gen_prompt(topic: str, need: int, have_titles: list[str], rnd: int) -> str:
    avoid = ("\nDo NOT repeat these already-collected papers:\n- " + "\n- ".join(have_titles[:40])
             if have_titles else "")
    angle = ("" if rnd == 0 else
             "\nThis is a follow-up round: cover DIFFERENT sub-areas, methods, adjacent fields, "
             "older foundational work, and recent (2020+) studies you did not list before.")
    return (
        f"You are building the reference list for a research paper on: {topic}\n\n"
        f"List {max(need + 8, 20)} REAL, published, peer-reviewed journal articles or well-known "
        f"papers relevant to this topic — ones you are confident actually exist (correct title and "
        f"first author). Spread across the core question, methods, and related sub-areas.{angle}{avoid}\n\n"
        f"Write `{CANDIDATES_FILE}` as JSON: "
        '{"candidates": [{"title": "<exact paper title>", "author": "<first author surname>", '
        '"year": <year>}, ...]}. '
        "Do NOT invent DOIs (they will be looked up and verified — a made-up paper will be dropped). "
        "Give your honest best-known real titles. End with CHILD_OK.")


def collect(run_dir: Path, topic: str, brain: Any, *, target: int = 40, max_rounds: int = 3,
            seed_dois: list[dict[str, Any]] | None = None,
            pause: float = 0.34) -> dict[str, Any]:
    """codex GENERATES candidate papers -> CrossRef VERIFIES them -> loop until `target`
    real, de-duplicated references (or rounds run out). `seed_dois` pre-loads already-real
    references (e.g. the OpenAlex corpus) so this is a SUPPLEMENT, not a replacement.
    Returns {refs: [{doi,title,year}], rounds, verified, requested}. brain(prompt, writes)
    must write CANDIDATES_FILE (the lane's brain dispatch)."""
    run_dir = Path(run_dir)
    seen: set[str] = set()
    topic_terms = _title_tokens(topic)        # on-FIELD relevance check for every verified ref
    refs: list[dict[str, Any]] = []
    for s in (seed_dois or []):
        d = str(s.get("doi") or "").strip().lower()
        if d and d not in seen:
            seen.add(d)
            refs.append({"doi": d, "title": s.get("title"), "year": s.get("year")})
    requested = 0
    rounds = 0
    for rnd in range(max_rounds):
        if len(refs) >= target:
            break
        rounds = rnd + 1
        need = target - len(refs)
        have_titles = [r.get("title") for r in refs if r.get("title")]
        ok = brain(_gen_prompt(topic, need, have_titles, rnd), [CANDIDATES_FILE])
        cands = _read_candidates(run_dir)
        requested += len(cands)
        refs.extend(verify_candidates(cands, pause=pause, seen=seen, topic_terms=topic_terms))
    return {"refs": refs, "rounds": rounds, "verified": len(refs), "requested": requested}
