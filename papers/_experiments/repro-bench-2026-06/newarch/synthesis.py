#!/usr/bin/env python3
"""Generic, topic-agnostic evidence-synthesis library.

The meta-analysis math is field-independent (an effect size is an effect size,
whether the topic is wearables or statins) — this module is therefore reusable
across ALL topics within a synthesis type, and adding a new synthesis TYPE is a
one-time, topic-agnostic addition (never a per-topic rebuild). Everything
per-topic (PICOS eligibility, moderators, the query) comes from the contract;
everything here is universal.

Synthesis types (each a distinct pooling model over one DerSimonian-Laird core):
- intervention : ratio (OR/RR/HR, log scale) + mean difference (SMD/MD, raw)
- prevalence   : single proportion (logit transform)
- correlation  : Pearson r (Fisher z) + risk associations (OR/HR, log scale)
- diagnostic   : sensitivity & specificity pooled separately (logit proportion)

Every extracted effect keeps its verbatim evidence sentence (auditable; nothing
is paraphrased). No LLM is used anywhere in this module.
"""
from __future__ import annotations

import math
import re
from typing import Any, Callable

Z95 = 1.959963985


# ── DerSimonian-Laird random-effects core (operates on a chosen scale) ────────

def dl_pool(ys: list[float], ses: list[float]) -> dict[str, Any] | None:
    """Random-effects pooling on whatever scale the caller transformed to.
    Returns pooled estimate (still on that scale) + heterogeneity. >=2 needed."""
    rows = [(y, s) for y, s in zip(ys, ses) if s and s > 0 and math.isfinite(y)]
    if len(rows) < 2:
        return None
    ys, ses = [r[0] for r in rows], [r[1] for r in rows]
    w = [1 / (s * s) for s in ses]
    fixed = sum(wi * yi for wi, yi in zip(w, ys)) / sum(w)
    q = sum(wi * (yi - fixed) ** 2 for wi, yi in zip(w, ys))
    df = len(rows) - 1
    c = sum(w) - sum(wi * wi for wi in w) / sum(w)
    tau2 = max(0.0, (q - df) / c) if c > 0 else 0.0
    wre = [1 / (s * s + tau2) for s in ses]
    pooled = sum(wi * yi for wi, yi in zip(wre, ys)) / sum(wre)
    se_pool = math.sqrt(1 / sum(wre))
    i2 = max(0.0, (q - df) / q) * 100 if q > 0 else 0.0
    return {"k": len(rows), "y": pooled, "se": se_pool,
            "ci_low_y": pooled - Z95 * se_pool, "ci_high_y": pooled + Z95 * se_pool,
            "i2_percent": round(i2, 1), "tau2": round(tau2, 4), "q": round(q, 3)}


# ── scale transforms: (effect dict) -> (y, se) on the pooling scale ───────────

def _se_from_ci(lo: float, hi: float, transform: Callable[[float], float]) -> float | None:
    if lo is None or hi is None or hi <= lo:
        return None
    return (transform(hi) - transform(lo)) / (2 * Z95)


def _prep_log_ratio(e: dict[str, Any]) -> tuple[float, float] | None:
    eff = e.get("effect")
    if not eff or eff <= 0:
        return None
    se = _se_from_ci(e.get("ci_low"), e.get("ci_high"), math.log)
    return (math.log(eff), se) if se else None


def _prep_raw(e: dict[str, Any]) -> tuple[float, float] | None:
    if e.get("ci_low") is None or e.get("ci_high") is None:
        return None
    se = _se_from_ci(e["ci_low"], e["ci_high"], lambda x: x)
    return (float(e["effect"]), se) if se else None


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _prep_proportion(e: dict[str, Any]) -> tuple[float, float] | None:
    p = e.get("effect")
    if p is None or not (0 < p < 1):
        return None
    if e.get("ci_low") is not None and e.get("ci_high") is not None and e["ci_high"] > e["ci_low"]:
        se = _se_from_ci(e["ci_low"], e["ci_high"], _logit)
        if se:
            return (_logit(p), se)
    n = e.get("n")
    if n and n > 0:                      # SE of logit(p) = 1/sqrt(n p (1-p))
        return (_logit(p), 1 / math.sqrt(n * p * (1 - p)))
    return None


def _prep_correlation(e: dict[str, Any]) -> tuple[float, float] | None:
    r = e.get("effect")
    n = e.get("n")
    if r is None or abs(r) >= 1 or not n or n <= 3:
        return None
    return (math.atanh(r), 1 / math.sqrt(n - 3))   # Fisher z


_TRANSFORMS = {
    "log_ratio": (_prep_log_ratio, math.exp),
    "smd": (_prep_raw, lambda y: y),    # standardized -> comparable across studies
    "md": (_prep_raw, lambda y: y),     # raw units -> NOT poolable across heterogeneous scales
    "raw": (_prep_raw, lambda y: y),    # legacy alias (kept for back-compat)
    "proportion": (_prep_proportion, lambda y: 1 / (1 + math.exp(-y))),
    "correlation": (_prep_correlation, math.tanh),
}

# Raw mean differences live on each study's original outcome scale; pooling them
# across studies is only valid when the scale is identical, which abstract-level
# extraction cannot verify. So MD is extracted + reported per-study but NOT pooled.
NON_POOLABLE_SCALES = {"md"}


def pool(effects: list[dict[str, Any]], scale: str) -> dict[str, Any] | None:
    """Pool a homogeneous set of effects on the named scale, back-transforming
    the pooled estimate + CI to the natural scale. De-dupes to one effect per
    study (a multi-effect study is not independent evidence)."""
    prep, back = _TRANSFORMS[scale]
    seen: set[str] = set()
    ys: list[float] = []
    ses: list[float] = []
    used: list[dict[str, Any]] = []
    for e in effects:
        study = str(e.get("doi") or e.get("title") or id(e))
        if study in seen:
            continue
        pr = prep(e)
        if pr is None:
            continue
        seen.add(study)
        ys.append(pr[0])
        ses.append(pr[1])
        used.append(e)
    res = dl_pool(ys, ses)
    if not res:
        return None
    return {
        "k": res["k"], "scale": scale,
        "method": f"DerSimonian-Laird random effects ({scale})",
        "pooled_effect": round(back(res["y"]), 4),
        "ci_low": round(back(res["ci_low_y"]), 4),
        "ci_high": round(back(res["ci_high_y"]), 4),
        "i2_percent": res["i2_percent"], "tau2": res["tau2"], "q": res["q"],
        "_ys": ys, "_ses": ses, "_studies": [e.get("doi") or e.get("title") for e in used],
    }


# ── generic sensitivity / small-study analyses (operate on pooled _ys/_ses) ───

def egger_test(pooled: dict[str, Any]) -> dict[str, Any] | None:
    """Egger's regression test for small-study effects: regress (y/se) on (1/se);
    the intercept's t-test flags funnel asymmetry. Needs k>=3."""
    ys, ses = pooled.get("_ys") or [], pooled.get("_ses") or []
    if len(ys) < 3:
        return None
    x = [1 / s for s in ses]
    y = [yi / si for yi, si in zip(ys, ses)]
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0:
        return None
    slope = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / sxx
    intercept = my - slope * mx
    resid = [yi - (intercept + slope * xi) for xi, yi in zip(x, y)]
    s2 = sum(r * r for r in resid) / (n - 2) if n > 2 else 0.0
    se_int = math.sqrt(s2 * (1 / n + mx * mx / sxx)) if s2 > 0 else 0.0
    t = intercept / se_int if se_int > 0 else 0.0
    return {"intercept": round(intercept, 3), "t": round(t, 3), "df": n - 2,
            "interpretation": "possible small-study/publication bias" if abs(t) > 2
            else "no strong funnel asymmetry detected"}


def leave_one_out(effects: list[dict[str, Any]], scale: str) -> list[dict[str, Any]]:
    """Re-pool omitting each study in turn — shows whether one study drives the result."""
    seen: dict[str, list[dict[str, Any]]] = {}
    for e in effects:
        seen.setdefault(str(e.get("doi") or e.get("title") or id(e)), []).append(e)
    out: list[dict[str, Any]] = []
    keys = list(seen)
    if len(keys) < 3:
        return out
    for omit in keys:
        subset = [e for k in keys if k != omit for e in seen[k]]
        p = pool(subset, scale)
        if p:
            out.append({"omitted": (seen[omit][0].get("title") or omit)[:80],
                        "pooled_effect": p["pooled_effect"],
                        "ci_low": p["ci_low"], "ci_high": p["ci_high"], "k": p["k"]})
    return out


def subgroup(effects: list[dict[str, Any]], scale: str, key: str) -> dict[str, Any]:
    """Pool within each level of a moderator (effects carry the key, e.g.
    'outcome_domain' or 'device_type'). Levels with <2 studies are skipped."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for e in effects:
        groups.setdefault(str(e.get(key) or "unspecified"), []).append(e)
    out: dict[str, Any] = {}
    for level, rows in groups.items():
        p = pool(rows, scale)
        if p:
            out[level] = {"k": p["k"], "pooled_effect": p["pooled_effect"],
                          "ci_low": p["ci_low"], "ci_high": p["ci_high"],
                          "i2_percent": p["i2_percent"]}
    return out


# ── per-type effect extraction (regex over abstracts; verbatim evidence kept) ─

_NUM = r"(-?\d+(?:\.\d+)?)"
_CI = r"[\s,;(]{0,5}95\s*%\s*(?:CI|confidence interval)[\s=:,]*" + _NUM + r"\s*(?:[-–—]|to|,)\s*" + _NUM
_N = re.compile(r"\b[nN]\s*=\s*(\d{2,7})\b")

_RATIO = re.compile(
    r"\b(aOR|OR|aRR|RR|aHR|HR|odds ratio|risk ratio|relative risk|hazard ratio)\b[\s=:,]*"
    + _NUM + _CI, re.I)
_SMD = re.compile(
    r"\b(Cohen'?s\s*d|SMD|MD|standardi[sz]ed mean difference|mean difference)\b[\s=:,]*"
    + _NUM + r"(?:" + _CI + r")?", re.I)
_PREV = re.compile(
    r"\b(prevalence|pooled prevalence|proportion)\b[^.]{0,40}?" + _NUM + r"\s*%"
    + r"(?:[\s,;(]{0,5}95\s*%\s*(?:CI|confidence interval)[\s=:,]*" + _NUM + r"\s*(?:[-–—]|to|,)\s*"
    + _NUM + r"\s*%?)?", re.I)
_CORR = re.compile(
    r"\b(r|correlation coefficient|Pearson'?s?\s*r|Spearman'?s?)\b[\s=:]*"
    + r"(-?0?\.\d+)", re.I)
_SENS = re.compile(r"\b(sensitivity|specificity)\b[^.]{0,30}?" + _NUM + r"\s*%?", re.I)
_MEASURE_CANON = {"odds ratio": "OR", "risk ratio": "RR", "relative risk": "RR",
                  "hazard ratio": "HR", "aor": "OR", "arr": "RR", "ahr": "HR"}


def _ev(text: str, start: int) -> str:
    left = max(text.rfind(". ", 0, start), 0)
    right = text.find(". ", start)
    return text[left:right if right != -1 else len(text)].strip(" .")[:300]


def _tag_moderators(effect: dict[str, Any], low_abstract: str,
                    moderators: list[dict[str, Any]]) -> None:
    """Tag an effect with the level of each contract-defined moderator whose
    keywords appear in the abstract, so subgroup analysis can group by it. The
    keyword->level maps come from the contract (e.g. delivery_mode: digital vs
    face_to_face) — never hardcoded, so this stays generic across topics. The
    first moderator also fills outcome_domain (the default subgroup key)."""
    for i, mod in enumerate(moderators):
        name = str(mod.get("name") or "").strip()
        levels = mod.get("levels") if isinstance(mod.get("levels"), dict) else {}
        if not name or not levels:
            continue
        matched = next((lvl for lvl, kws in levels.items()
                        if any(str(k).lower() in low_abstract for k in (kws or []))),
                       "unspecified")
        effect[name] = matched
        if i == 0 and not effect.get("outcome_domain"):
            effect["outcome_domain"] = matched


def extract(synthesis_type: str, abstract: str, work: dict[str, Any],
            moderators: list[dict[str, Any]] | None = None,
            outcome_terms: list[str] | None = None) -> list[dict[str, Any]]:
    """Mechanical extraction dispatched by synthesis type. Each effect carries
    measure, value, CI (when present), n, scale, a verbatim evidence sentence,
    and any contract-defined moderator tags (for subgroup analysis).

    outcome_terms (optional) gates ONLY non-poolable raw MD effects: a mean
    difference whose evidence sentence never names the outcome is almost always a
    secondary/off-topic measure (e.g. a knee-fitness MD inside a depression review).
    Poolable effects (smd/ratio/r/proportion) are never dropped here, so k — the
    scarce quantity at abstract level — is fully preserved regardless of this filter."""
    if not abstract:
        return []
    nm = _N.search(abstract)
    n = int(nm.group(1)) if nm else None
    meta = {"n": n, "title": (work.get("title") or "")[:160],
            "year": work.get("publication_year"), "doi": work.get("doi")}
    out: list[dict[str, Any]] = []

    def add(**kw: Any) -> None:
        out.append({**meta, **kw, "evidence": _ev(abstract, kw.pop("_start", 0))})

    if synthesis_type in ("intervention", "correlation"):
        for m in _RATIO.finditer(abstract):
            pt, lo, hi = float(m.group(2)), float(m.group(3)), float(m.group(4))
            if 0 < lo <= pt <= hi:
                add(measure=_MEASURE_CANON.get(m.group(1).lower(), m.group(1).upper()),
                    effect=pt, ci_low=lo, ci_high=hi, scale="log_ratio", _start=m.start())
    if synthesis_type == "intervention":
        for m in _SMD.finditer(abstract):
            lo = float(m.group(3)) if m.group(3) else None
            hi = float(m.group(4)) if m.group(4) else None
            if lo is not None and hi is not None and not (lo <= float(m.group(2)) <= hi):
                lo = hi = None
            raw = m.group(1).lower()
            is_md = raw in ("md", "mean difference")
            add(measure="MD" if is_md else "SMD",
                effect=float(m.group(2)), ci_low=lo, ci_high=hi,
                scale="md" if is_md else "smd", _start=m.start())
    if synthesis_type == "correlation":
        for m in _CORR.finditer(abstract):
            r = float(m.group(2))
            if abs(r) < 1:
                add(measure="r", effect=r, ci_low=None, ci_high=None,
                    scale="correlation", _start=m.start())
    if synthesis_type == "prevalence":
        for m in _PREV.finditer(abstract):
            p = float(m.group(2)) / 100.0
            lo = float(m.group(3)) / 100.0 if m.group(3) else None
            hi = float(m.group(4)) / 100.0 if m.group(4) else None
            if 0 < p < 1:
                add(measure="prevalence", effect=p, ci_low=lo, ci_high=hi,
                    scale="proportion", _start=m.start())
    if synthesis_type == "diagnostic":
        for m in _SENS.finditer(abstract):
            v = float(m.group(2))
            p = v / 100.0 if v > 1 else v
            if 0 < p <= 1:
                add(measure=m.group(1).lower(), effect=p, ci_low=None, ci_high=None,
                    scale="proportion", outcome_domain=m.group(1).lower(), _start=m.start())
    if outcome_terms:
        ot = [t.lower() for t in outcome_terms if t]
        if ot:
            out = [e for e in out if e.get("scale") != "md"
                   or any(t in (e.get("evidence") or "").lower() for t in ot)]
    if moderators:
        low = abstract.lower()
        for e in out:
            _tag_moderators(e, low, moderators)
    # cap per study to avoid table-mining one abstract
    return out[:4]


SYNTHESIS_TYPES = ("intervention", "prevalence", "correlation", "diagnostic")


# ── PICOS eligibility screen (criteria come from the contract, not hardcoded) ─

def screen_picos(work_text: str, picos: dict[str, Any]) -> tuple[bool, str]:
    """Generic eligibility screen. `picos` is the contract's spec, e.g.
    {"exclude_terms": ["pediatric","children","cerebral palsy"],
     "require_any": ["randomized","randomised","controlled trial","rct"],
     "require_all": ["mindfulness","anxiety"]}.
    - exclude_terms: any hit -> excluded (Population/design exclusions).
    - require_any: at least one must appear (e.g. a study-design family).
    - require_all: EVERY term must appear — this is the on-topic gate. Without it,
      a "randomized + controlled trial" screen alone pools dietary/massage/smoking
      studies into a mindfulness-anxiety review. The intervention + outcome concept
      belong here so the pool is actually about the topic.
    Returns (eligible, reason). Topic-specific terms live in the contract; this
    function is universal."""
    text = work_text.lower()
    for term in (picos.get("exclude_terms") or []):
        if term.lower() in text:
            return False, f"excluded: matches '{term}'"
    req = [t.lower() for t in (picos.get("require_any") or [])]
    if req and not any(t in text for t in req):
        return False, f"excluded: none of require_any {req}"
    # require_all: AND across concepts, OR within. Each element is either a string
    # (must appear) or a list of synonyms (at least one must appear). This lets the
    # on-topic gate demand both intervention AND outcome while tolerating phrasing:
    # [["mindfulness","mbsr","mbct","meditation"], ["anxiety","anxious"]].
    for concept in (picos.get("require_all") or []):
        if isinstance(concept, (list, tuple)):
            syns = [str(s).lower() for s in concept]
            if syns and not any(s in text for s in syns):
                return False, f"excluded: missing concept (none of {syns})"
        elif str(concept).lower() not in text:
            return False, f"excluded: missing required term '{concept}'"
    return True, "eligible"
