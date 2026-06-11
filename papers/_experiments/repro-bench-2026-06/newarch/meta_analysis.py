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

MAILTO = "aicooperation.tw@gmail.com"
OPENALEX_WORKS = "https://api.openalex.org/works"
UA = f"paperbench/1.0 (mailto:{MAILTO})"
PER_PAGE = 200
MIN_STUDIES_TO_COMPLETE = 3  # fewer extractable studies -> blocked (fail-closed)

# Strict effect patterns. Group layout: measure, point, ci_low, ci_high.
_NUM = r"(\d+(?:\.\d+)?)"
RATIO_RE = re.compile(
    r"\b(OR|aOR|RR|aRR|HR|aHR|odds ratio|risk ratio|relative risk|hazard ratio)\b"
    r"[\s=:,]*" + _NUM +
    r"[\s,;(]{0,4}(?:95\s*%\s*(?:CI|confidence interval))[\s=:,]*" + _NUM +
    r"\s*(?:[-–—]|to|,)\s*" + _NUM,
    re.IGNORECASE)
SMD_RE = re.compile(
    r"\b(Cohen'?s\s*d|SMD|MD|standardi[sz]ed mean difference|mean difference|effect size)\b"
    r"[\s=:,]*(-?\d+(?:\.\d+)?)"
    r"(?:[\s,;(]{0,4}95\s*%\s*(?:CI|confidence interval)[\s=:,]*(-?\d+(?:\.\d+)?)"
    r"\s*(?:[-–—]|to|,)\s*(-?\d+(?:\.\d+)?))?", re.IGNORECASE)
N_RE = re.compile(r"\b[nN]\s*=\s*(\d{2,7})\b")
MEASURE_CANON = {"odds ratio": "OR", "risk ratio": "RR", "relative risk": "RR",
                 "hazard ratio": "HR", "aor": "OR", "arr": "RR", "ahr": "HR"}


def _get(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def reconstruct_abstract(inv: dict[str, list[int]] | None) -> str:
    if not isinstance(inv, dict) or not inv:
        return ""
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def collect(topic: str, max_works: int = 400, timeout: int = 30) -> tuple[list[dict[str, Any]], int]:
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


def _sentence_of(text: str, span_start: int) -> str:
    left = max(text.rfind(". ", 0, span_start), 0)
    right = text.find(". ", span_start)
    return text[left:right if right != -1 else len(text)].strip(" .")[:300]


def extract_effects(work: dict[str, Any]) -> list[dict[str, Any]]:
    """Mechanical extraction; each effect carries its verbatim evidence sentence."""
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    if not abstract:
        return []
    n_match = N_RE.search(abstract)
    n = int(n_match.group(1)) if n_match else None
    out: list[dict[str, Any]] = []
    for m in RATIO_RE.finditer(abstract):
        raw = m.group(1).lower()
        measure = MEASURE_CANON.get(raw, raw.upper())
        point, lo, hi = (float(m.group(i)) for i in (2, 3, 4))
        if not (0 < lo <= point <= hi) or lo <= 0:
            continue  # malformed/implausible -> never admit
        out.append({"measure": measure, "effect": point, "ci_low": lo, "ci_high": hi,
                    "n": n, "title": (work.get("title") or "")[:160],
                    "year": work.get("publication_year"), "doi": work.get("doi"),
                    "evidence": _sentence_of(abstract, m.start())})
    if not out:
        for m in SMD_RE.finditer(abstract):
            raw = m.group(1).lower()
            measure = "MD" if raw in ("md", "mean difference") else "SMD"
            point = float(m.group(2))
            lo = float(m.group(3)) if m.group(3) is not None else None
            hi = float(m.group(4)) if m.group(4) is not None else None
            if lo is not None and hi is not None and not (lo <= point <= hi):
                lo = hi = None  # malformed CI -> keep the point, never pool it
            out.append({"measure": measure, "effect": point,
                        "ci_low": lo, "ci_high": hi, "n": n,
                        "title": (work.get("title") or "")[:160],
                        "year": work.get("publication_year"), "doi": work.get("doi"),
                        "evidence": _sentence_of(abstract, m.start())})
    return out[:3]  # at most a few effects per study (avoid table-mining one abstract)


RATIO_MEASURES = {"OR", "RR", "HR"}


def pool_random_effects(measure: str, effects: list[dict[str, Any]]) -> dict[str, Any] | None:
    """DerSimonian-Laird random-effects pooling of one measure group. Ratio
    measures (OR/RR/HR) pool on the log scale; SMD/MD pool on the raw scale.
    SE is derived from each study's 95% CI; >=2 studies with CIs required."""
    log_scale = measure in RATIO_MEASURES
    rows = [e for e in effects if e.get("ci_low") is not None and e.get("ci_high") is not None
            and e["ci_high"] > e["ci_low"] and (not log_scale or e["ci_low"] > 0)]
    # A pool of effects from a single study is a study summary, not a
    # meta-analysis (r5 reviewer finding). Require >=2 DISTINCT studies; when a
    # study contributes several effects keep only its first (avoids treating
    # within-study effects as independent evidence).
    seen_studies: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for e in rows:
        study = str(e.get("doi") or e.get("title") or "")
        if study in seen_studies:
            continue
        seen_studies.add(study)
        deduped.append(e)
    rows = deduped
    if len(rows) < 2:
        return None
    if log_scale:
        y = [math.log(e["effect"]) for e in rows]
        se = [(math.log(e["ci_high"]) - math.log(e["ci_low"])) / (2 * 1.959964) for e in rows]
    else:
        y = [float(e["effect"]) for e in rows]
        se = [(e["ci_high"] - e["ci_low"]) / (2 * 1.959964) for e in rows]
    if any(s <= 0 for s in se):
        return None
    w = [1 / (s * s) for s in se]
    fixed = sum(wi * yi for wi, yi in zip(w, y)) / sum(w)
    q = sum(wi * (yi - fixed) ** 2 for wi, yi in zip(w, y))
    dfree = len(rows) - 1
    c = sum(w) - sum(wi * wi for wi in w) / sum(w)
    tau2 = max(0.0, (q - dfree) / c) if c > 0 else 0.0
    w_re = [1 / (s * s + tau2) for s in se]
    pooled = sum(wi * yi for wi, yi in zip(w_re, y)) / sum(w_re)
    se_pooled = math.sqrt(1 / sum(w_re))
    i2 = max(0.0, (q - dfree) / q) * 100 if q > 0 else 0.0
    lo, hi = pooled - 1.959964 * se_pooled, pooled + 1.959964 * se_pooled
    if log_scale:
        pooled, lo, hi = math.exp(pooled), math.exp(lo), math.exp(hi)
    return {
        "k": len(rows),
        "method": f"DerSimonian-Laird random effects ({'log' if log_scale else 'raw'} scale)",
        "pooled_effect": round(pooled, 3),
        "ci_low": round(lo, 3), "ci_high": round(hi, 3),
        "i2_percent": round(i2, 1), "tau2": round(tau2, 4), "q": round(q, 2),
    }


def run(topic: str, out_dir: Path, max_works: int = 400) -> dict[str, Any]:
    started = time.time()
    out_dir = out_dir.expanduser().resolve()
    (out_dir / "real_experiments").mkdir(parents=True, exist_ok=True)

    def finish(result: dict[str, Any]) -> dict[str, Any]:
        (out_dir / "real_experiments" / "real_results.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return result

    try:
        works, total = collect(topic, max_works)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return finish({"status": "blocked", "simulated": False, "source": "OpenAlex",
                       "reason": f"collection failed: {exc}", "topic": topic})

    effects: list[dict[str, Any]] = []
    screened = 0
    for w in works:
        if w.get("abstract_inverted_index"):
            screened += 1
        effects.extend(extract_effects(w))
    studies = {(e["doi"] or e["title"]) for e in effects}

    if len(studies) < MIN_STUDIES_TO_COMPLETE:
        return finish({"status": "blocked", "simulated": False, "source": "OpenAlex",
                       "reason": f"only {len(studies)} studies with extractable quantitative "
                                 f"effects (need >= {MIN_STUDIES_TO_COMPLETE}); abstract-level "
                                 "meta-analysis not viable for this topic",
                       "topic": topic,
                       "prisma": {"identified": total, "scanned": len(works),
                                  "with_abstract": screened, "studies_with_effects": len(studies)}})

    by_measure: dict[str, list[dict[str, Any]]] = {}
    for e in effects:
        by_measure.setdefault(e["measure"], []).append(e)
    pooled = {m: p for m, rows in by_measure.items()
              if (p := pool_random_effects(m, rows)) is not None}

    # Background literature for the paper's bibliography: the most-cited works of
    # the scanned corpus (real DOIs; a verifies + completes them downstream). A
    # meta-analysis must cite far more than its included studies.
    effect_dois = {str(e.get("doi") or "").lower() for e in effects}
    background = sorted(
        (w for w in works if w.get("doi") and str(w["doi"]).lower() not in effect_dois),
        key=lambda w: -(w.get("cited_by_count") or 0))[:30]
    background_works = [{"title": (w.get("title") or "")[:160], "doi": w.get("doi"),
                         "year": w.get("publication_year"),
                         "cited_by": w.get("cited_by_count")} for w in background]

    return finish({
        "status": "completed", "simulated": False, "source": "OpenAlex",
        "source_type": "literature", "lane": "meta_analysis",
        "rows": len(works),
        "meta": {
            "topic": topic,
            "prisma": {"identified": total, "scanned": len(works),
                       "with_abstract": screened, "studies_with_effects": len(studies),
                       "effects_extracted": len(effects)},
            "effects": effects,
            "background_works": background_works,
            "by_measure_counts": {m: len(v) for m, v in by_measure.items()},
            "pooled": pooled,
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
