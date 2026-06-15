"""Paper-pack gate-check helpers (DESIGN §3.7–§3.8): the REAL A–F checks.

Each helper is a pure ``check(dossier) -> GateResult``. ``pack.py`` registers them;
the framework's ``run_gates`` lifecycle runs + enforces them. Helpers live here (not
in ``pack.py``) to keep the pack focused (coding-style: many small files).

Every helper FAILS CLOSED on bad/missing input — a BLOCK gate with nothing to check
returns ``passed=False, p0=True`` (a weak worker cannot make a gate vanish by handing
it an empty dossier). The single WARN gate (E) annotates, never blocks.

Dossier keys each gate reads (the agent↔determinism interface, §3.7):

    Gate A (refs)   evidence.references = {bib_count, doi_real_rate}
    Gate B (claim)  draft_text   : str   — the actual prose to independently extract from
                    claim_evidence: list — the agent-filled Claim×Evidence matrix rows
                    real_results  : dict — meta/real_results JSON (numbers ground truth)
    Gate C (figure) evidence.figures: list[{name, svg, png, in_figure_numbers?}]
                    qmd_text      : str  — to detect duplicate figure embeds (dedup)
                    real_results  : dict — in-figure numbers must equal these
    Gate D (read)   draft_text   : str   — placeholder / under-length / completeness
                    render_ok     : bool — optional; False => render-fail block
    Gate E (value)  viability     : dict — {max_poolable_k, poolable_k, ...} (WARN)
                    value_floor   : int  — optional override of POOLABLE_FLOOR
                    (writes a value_adjustment_log entry into the GateResult evidence)
    Gate F (logic)  draft_text   : str   — the prose the 7-scan audits
                    real_results  : dict — number-traceability source for Scan 2
"""
from __future__ import annotations

import re
from typing import Any

from framework import GateResult, Severity

from . import logic_audit

# ── thresholds (DESIGN §3.8) ─────────────────────────────────────────────────
REFS_FLOOR = 35
DOI_REAL_RATE_FLOOR = 0.80
POOLABLE_FLOOR = 5            # Gate E: max poolable-k below this => value-insufficient
PROSE_WORD_FLOOR = 3000       # Gate D: a paper body under this is "too thin" (matches compile_review)
PLACEHOLDER_MARKERS = ("PLACEHOLDER", "[placeholder]", "TODO:", "TODO ", "TBD",
                       "lorem ipsum", "XXX", "FIXME", "<!-- todo")
NUMBER_TOLERANCE = 1e-6       # Gate B/C exact-match tolerance


# ───────────────────────────── shared utilities ─────────────────────────────
def _extract_numbers_from_results(real_results: Any) -> set[float]:
    """All numbers reachable in the real_results JSON (Gate B/C ground truth)."""
    acc: set[float] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            acc.add(float(obj))
            acc.add(abs(float(obj)))            # claims often drop the sign of an SMD
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)
        elif isinstance(obj, str):
            for m in re.finditer(r"-?\d+(?:\.\d+)?", obj):
                try:
                    f = float(m.group())
                    acc.add(f)
                    acc.add(abs(f))
                except ValueError:
                    pass

    walk(real_results)
    return acc


def _number_in_results(value: float, source: set[float]) -> bool:
    """Exact-match a claimed number to a result number within tolerance.

    Reported numbers are routinely ROUNDED in prose (-0.4327 -> -0.43, 95.4 -> 95),
    so a claim matches if it equals a result number to the claim's own decimal
    precision (the claim is "exact" w.r.t. how it was written). Trailing-digit
    truncation of an exact result is therefore accepted; a genuinely different
    number (1,200 vs 24) is not.
    """
    if not source:
        return False
    # decimals the CLAIM was written with -> rounding bucket for that claim
    decimals = 0
    s = f"{value:.10f}".rstrip("0")
    if "." in s:
        decimals = len(s.split(".", 1)[1])
    tol = max(NUMBER_TOLERANCE, 0.5 * (10 ** -decimals), abs(value) * 1e-3)
    return any(abs(value - r) <= tol for r in source)


_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _prose_only(draft_text: str) -> str:
    """Strip HTML comments + YAML frontmatter so audits/extractors see PROSE only
    (fixture/editor comments and frontmatter are not author claims)."""
    text = draft_text or ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    return _COMMENT_RE.sub(" ", text)


# ───────────────────────────── Gate A: contract/refs ────────────────────────
def gate_refs(dossier: dict[str, Any]) -> GateResult:
    """A (BLOCK): refs>=35 AND doi_real_rate>=0.80. Fail-closed if evidence absent."""
    refs = (dossier.get("evidence") or {}).get("references") or {}
    n = int(refs.get("bib_count") or 0)
    rate = refs.get("doi_real_rate")
    ok = n >= REFS_FLOOR and (rate is None or rate >= DOI_REAL_RATE_FLOOR)
    return GateResult(
        gate="A", severity=Severity.BLOCK, passed=ok, p0=not ok,
        details=f"bib_count={n} (floor {REFS_FLOOR}), doi_real_rate={rate} (floor {DOI_REAL_RATE_FLOOR})",
        evidence={"bib_count": n, "doi_real_rate": rate})


# ───────────────────────────── Gate B: claim <= evidence ────────────────────
# Independent claim extractor (anti-gaming, §3.7): pull quantitative claims straight
# from the prose so an UNLISTED claim the agent forgot cannot slip past the matrix.
_UNIVERSAL_QUANTIFIERS = (
    "always", "every", "all ", "all.", "all,", "none", "never", "any ",
    "regardless of", "in all cases", "universally", "without exception",
)
_STRONG_CAUSAL = (
    "prove", "proves", "proven", "cause", "causes", "caused", "causal",
    "guarantee", "guarantees", "ensures that", "demonstrates that",
)
_OVERREACH_SCOPE = (
    "state-of-the-art", "state of the art", "outperform", "outperforms",
    "outperforming", "first-line", "every public leaderboard", "all prior work",
    "best-in-class", "unprecedented",
)
_NUMBER_RE = re.compile(r"(?<![\w.])([≥≤<>]?\s*\d{1,7}(?:,\d{3})*(?:\.\d{1,4})?\s*[%×]?)(?![\w.])")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def _to_number(token: str) -> float | None:
    cleaned = re.sub(r"[≥≤<>%×,\s]", "", token)
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_claims(draft_text: str) -> list[dict[str, Any]]:
    """INDEPENDENTLY extract quantitative/scope claims from prose (no matrix trust).

    A sentence is a claim if it carries a quantitative number, a universal
    quantifier, a strong causal verb, or an overreach scope phrase. Returns a row
    per claim: ``{text, numbers, quantifier, causal, overreach}``.
    """
    claims: list[dict[str, Any]] = []
    if not draft_text:
        return claims
    prose = _prose_only(draft_text)
    for raw in _SENTENCE_SPLIT.split(prose.replace("\n", " ")):
        sent = raw.strip()
        if len(sent) < 12:
            continue
        low = sent.lower()
        numbers = [n for n in (_to_number(m.group(1)) for m in _NUMBER_RE.finditer(sent))
                   if n is not None and n not in (0.0, 1.0)]
        quantifier = next((q.strip() for q in _UNIVERSAL_QUANTIFIERS if q in low), None)
        causal = next((v for v in _STRONG_CAUSAL if re.search(rf"\b{re.escape(v)}\b", low)), None)
        overreach = next((s for s in _OVERREACH_SCOPE if s in low), None)
        if numbers or quantifier or causal or overreach:
            claims.append({
                "text": sent[:240],
                "numbers": numbers,
                "quantifier": quantifier,
                "causal": causal,
                "overreach": overreach,
            })
    return claims


def _matrix_text(rows: list[dict[str, Any]]) -> str:
    """Flatten the agent-filled claim_evidence rows into searchable text."""
    parts: list[str] = []
    for r in rows or []:
        if isinstance(r, dict):
            parts.append(" ".join(str(v) for v in r.values()))
        else:
            parts.append(str(r))
    return "\n".join(parts).lower()


def _claim_listed(claim: dict[str, Any], matrix_text: str,
                  matrix_numbers: set[float]) -> bool:
    """Is this extracted claim covered by a matrix row? Number claims match by number;
    quantifier/causal/overreach claims match by a salient phrase from the sentence."""
    if claim["numbers"]:
        return all(
            any(abs(n - m) <= max(NUMBER_TOLERANCE, abs(n) * 1e-3) for m in matrix_numbers)
            for n in claim["numbers"]
        )
    # non-numeric overclaim: require a distinctive content word from the sentence in a row
    salient = [w for w in re.findall(r"[a-z]{5,}", claim["text"].lower())
               if w not in {"results", "method", "across", "study", "studies",
                            "evidence", "approach", "demonstrating"}]
    return any(w in matrix_text for w in salient[:6]) if salient else False


def gate_claim_evidence(dossier: dict[str, Any]) -> GateResult:
    """B (BLOCK, the spine): claim <= evidence with independent extraction.

    P0 if ANY of: (a) an extracted claim has NO matrix row (unlisted claim);
    (b) a claimed number does not exact-match real_results; (c) a universal
    quantifier / strong causal verb is used (these always exceed abstract-level
    evidence in this engine's contribution tier). Fail-closed on missing draft.
    """
    draft = dossier.get("draft_text")
    if not draft:
        return GateResult(gate="B", severity=Severity.BLOCK, passed=False, p0=True,
                          details="no draft_text to extract claims from (fail-closed)",
                          evidence={"reason": "missing_draft"})

    matrix_rows = dossier.get("claim_evidence") or []
    matrix_text = _matrix_text(matrix_rows)
    matrix_numbers = {n for n in (_to_number(m.group(1))
                                  for m in _NUMBER_RE.finditer(matrix_text)) if n is not None}
    result_numbers = _extract_numbers_from_results(dossier.get("real_results") or {})

    claims = extract_claims(draft)
    flagged: list[dict[str, Any]] = []
    for c in claims:
        reasons: list[str] = []
        if not _claim_listed(c, matrix_text, matrix_numbers):
            reasons.append("unlisted (no matrix row)")
        for n in c["numbers"]:
            # A number is evidenced if it is EITHER traceable to our results OR
            # carried by a matrix row (a cited background number's evidence is the
            # citation, not real_results). Flag only numbers with NO evidence
            # anywhere — otherwise Gate B false-flags legitimate literature numbers.
            in_matrix = any(abs(n - m) <= max(NUMBER_TOLERANCE, abs(n) * 1e-3)
                            for m in matrix_numbers)
            if not in_matrix and not _number_in_results(n, result_numbers):
                reasons.append(f"number {n} unevidenced (not in real_results or matrix)")
        if c["quantifier"]:
            reasons.append(f"universal quantifier '{c['quantifier']}' exceeds evidence")
        if c["causal"]:
            reasons.append(f"strong causal verb '{c['causal']}' exceeds evidence")
        if c["overreach"]:
            reasons.append(f"scope overreach '{c['overreach']}' not in evidence")
        if reasons:
            flagged.append({"claim": c["text"], "reasons": reasons})

    ok = not flagged
    return GateResult(
        gate="B", severity=Severity.BLOCK, passed=ok, p0=not ok,
        details=(f"{len(claims)} claims extracted; {len(flagged)} P0 overclaim(s)"
                 if not ok else f"{len(claims)} claims extracted; all <= evidence"),
        evidence={"extracted": len(claims), "flagged": flagged})


# ───────────────────────────── Gate C: figure quality ───────────────────────
def _figure_embed_counts(qmd_text: str) -> dict[str, int]:
    """Count how many times each ``figures/<file>`` is embedded (dedup detector)."""
    counts: dict[str, int] = {}
    for m in re.finditer(r"!\[[^\]]*\]\(figures/([^)]+)\)", qmd_text or ""):
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def gate_figures(dossier: dict[str, Any]) -> GateResult:
    """C (BLOCK): every figure has paired SVG+PNG, in-figure numbers == real_results,
    and NO duplicate embed survives in the qmd. Fail-closed if no figures registered.
    """
    figs = (dossier.get("evidence") or {}).get("figures") or []
    if not figs:
        return GateResult(gate="C", severity=Severity.BLOCK, passed=False, p0=True,
                          details="no figures registered (fail-closed)",
                          evidence={"n_figures": 0})

    result_numbers = _extract_numbers_from_results(dossier.get("real_results") or {})
    embed_counts = _figure_embed_counts(dossier.get("qmd_text") or "")
    problems: list[str] = []

    for f in figs:
        name = f.get("name") or "?"
        if not f.get("svg") or not f.get("png"):
            problems.append(f"{name}: missing SVG or PNG pair")
        for num in f.get("in_figure_numbers") or []:
            try:
                val = float(num)
            except (TypeError, ValueError):
                continue
            if result_numbers and not _number_in_results(val, result_numbers):
                problems.append(f"{name}: in-figure number {num} != real_results")

    dupes = {fname: c for fname, c in embed_counts.items() if c > 1}
    if dupes:
        problems.append(f"duplicate figure embed(s) survive in qmd: {dupes}")

    ok = not problems
    return GateResult(
        gate="C", severity=Severity.BLOCK, passed=ok, p0=not ok,
        details=(f"{len(figs)} figure(s) checked; {len(problems)} problem(s)"
                 if not ok else f"{len(figs)} figure(s): paired, numbers match, no dupes"),
        evidence={"n_figures": len(figs), "problems": problems,
                  "embed_counts": embed_counts})


# ───────────────────────────── Gate D: readability/render ────────────────────
def _prose_word_count(draft_text: str) -> int:
    """CJK-aware word count over prose (drops YAML frontmatter + fenced code),
    mirroring compile_review._qmd_prose_words so Gate D matches the content gate."""
    text = draft_text or ""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            text = parts[2]
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    cjk = len(re.findall(r"[一-鿿㐀-䶿]", text))
    latin = len(re.sub(r"[一-鿿㐀-䶿]", " ", text).split())
    return latin + cjk // 2


def gate_readability(dossier: dict[str, Any]) -> GateResult:
    """D (BLOCK): block on placeholder text, under-length body, or render-fail.

    Wraps the SAME signals as compile_review.py / mechanical_check.py (placeholder
    markers, prose word floor) but over the dossier draft so it runs pre-render.
    Fail-closed if there is no draft.
    """
    draft = dossier.get("draft_text")
    if not draft:
        return GateResult(gate="D", severity=Severity.BLOCK, passed=False, p0=True,
                          details="no draft_text to check (fail-closed)",
                          evidence={"reason": "missing_draft"})

    low = draft.lower()
    found = [m for m in PLACEHOLDER_MARKERS if m.lower() in low]
    words = _prose_word_count(draft)
    render_ok = dossier.get("render_ok", True)

    problems: list[str] = []
    if found:
        problems.append(f"placeholder text present: {found}")
    if words < PROSE_WORD_FLOOR:
        problems.append(f"body too thin: {words} words (floor {PROSE_WORD_FLOOR})")
    if render_ok is False:
        problems.append("render failed (render_ok=False)")

    ok = not problems
    return GateResult(
        gate="D", severity=Severity.BLOCK, passed=ok, p0=not ok,
        details=(f"{len(problems)} readability problem(s)" if not ok
                 else f"{words} words, no placeholders, render ok"),
        evidence={"words": words, "placeholders": found, "render_ok": render_ok,
                  "problems": problems})


# ───────────────────────────── Gate E: experiment value (WARN) ───────────────
def gate_value(dossier: dict[str, Any]) -> GateResult:
    """E (WARN, §3.8): is the result worth writing? Reuses the viability metric
    (max poolable-k). Over a THIN corpus (value-insufficient) this does NOT block —
    it annotates ADJUST-or-PAUSE and emits a ``value_adjustment_log`` entry so the
    steering is auditable. WARN never blocks.

    Fail-closed semantics for a WARN gate = ``passed=False`` (the steering signal
    fires) WITHOUT ``p0`` (it cannot block the deliverable).
    """
    viability = dossier.get("viability") or {}
    floor = int(dossier.get("value_floor") or POOLABLE_FLOOR)
    max_k = viability.get("max_poolable_k")
    if max_k is None:
        # derive from poolable_k map if only that was handed in
        pk = viability.get("poolable_k") or {}
        max_k = max(pk.values(), default=0) if isinstance(pk, dict) else 0

    sufficient = int(max_k or 0) >= floor
    log_entry: dict[str, Any] | None = None
    if not sufficient:
        log_entry = {
            "verdict": "value-insufficient",
            "action": "ADJUST-or-PAUSE",
            "reason": f"max poolable-k={max_k} < floor {floor}",
            "before": "framed as a definitive pooled estimate",
            "after": "reframe as null/limitations or broaden outcome family",
            "process": "Gate E early-framing check (§3.8); steer the question to the evidence",
        }

    return GateResult(
        gate="E", severity=Severity.WARN, passed=sufficient, p0=False,
        details=(f"value sufficient: max poolable-k={max_k} >= floor {floor}" if sufficient
                 else f"value INSUFFICIENT: max poolable-k={max_k} < floor {floor} -> ADJUST+log"),
        evidence={"max_poolable_k": max_k, "floor": floor,
                  "value_adjustment_log": log_entry})


# ───────────────────────────── Gate F: logic/coherence ──────────────────────
def gate_logic(dossier: dict[str, Any]) -> GateResult:
    """F (BLOCK): wrap the vendored 7-scan logic audit. P0 if the audit reports any
    FAIL item (unsourced number / strong-verb-small-N / contradiction / cherry-pick).
    Fail-closed if there is no draft to audit.
    """
    draft = dossier.get("draft_text")
    if not draft:
        return GateResult(gate="F", severity=Severity.BLOCK, passed=False, p0=True,
                          details="no draft_text to audit (fail-closed)",
                          evidence={"reason": "missing_draft"})

    # Run the audit with no on-disk result files, then re-grade its number-
    # traceability scan (Scan 2) against the in-memory real_results numbers below,
    # so Gate F is self-contained (no results/*.json required on disk).
    real_results = dossier.get("real_results") or {}
    table_data = dossier.get("table_rows") or []
    prose = _prose_only(draft)

    audit = logic_audit.run_audit(prose, result_files=[], table_data=table_data)

    # Re-grade Scan 2 (quantifiers) against the in-memory real_results numbers so the
    # number-traceability check is exact even without a results/*.json on disk.
    source_numbers = _extract_numbers_from_results(real_results)
    regraded_fail: list[dict[str, Any]] = []
    for f in audit["scan_results"]["quantifiers"]:
        val = _to_number(f.get("number", ""))
        traced = val is not None and _number_in_results(val, source_numbers)
        if "NO_SOURCE" in f.get("verdict", "") and not traced:
            regraded_fail.append({"scan": "quantifiers", **f})

    # Non-quantifier FAILs are independent of result_files; keep them as audited.
    other_fail = [f for f in audit["fail_items"] if f.get("scan") != "quantifiers"]
    fail_items = regraded_fail + other_fail
    total_fail = len(fail_items)

    ok = total_fail == 0
    return GateResult(
        gate="F", severity=Severity.BLOCK, passed=ok, p0=not ok,
        details=(f"logic audit: {total_fail} FAIL item(s)" if not ok
                 else "logic audit: 0 FAIL items (coherent)"),
        evidence={"total_fail": total_fail, "fail_items": fail_items[:20]})
