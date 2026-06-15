"""Insurance domain pack (#2, mapped from insurance-kb-v2) — ENGINE_GENERAL_SPEC §2.2.

Real-ish (NOT a stub, per ENGINE_BUILD_PLAN P1*): viability_probe extracts findings
from the KB docs and scores yield against tiers; the gate_registry runs real
BLOCK/WARN checks over a report body. Proves the DomainPack seam holds across a
SECOND real domain whose shape differs from paper (findings+sources, no pooling;
DOCX not PDF; KB sources not OpenAlex).
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Any

from framework import DomainPack, Gate, GateResult, Severity, ViabilityVerdict

TIERS = {"shallow": 5, "standard": 10, "deep": 15}
BODY_MIN_WORDS = 400               # body_too_thin floor for a VIP report
_FINDING_RE = re.compile(r"^>\s*finding:\s*(.+)$", re.MULTILINE)
_DATE_RE = re.compile(r"^date:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", re.MULTILINE)
_SRC_RE = re.compile(r"^source_url:\s*(\S+)", re.MULTILINE)
_STALE_RE = re.compile(r"^stale:\s*true", re.MULTILINE)
_FN_REF_RE = re.compile(r"\[\^([^\]]+)\](?!:)")        # inline [^N]
_FN_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:\s*(\S+)", re.MULTILINE)  # [^N]: url
# currency or comma-grouped/large number = a quantitative claim that must be cited
_NUM_RE = re.compile(r"[€$¥£]\s?[0-9][0-9,.]*|[0-9]{1,3}(?:,[0-9]{3})+\s?億?|[0-9]+\s?億")


# ── findings extraction (real, from the KB docs) ─────────────────────────────
def _extract_findings_from_kb(kb_dir: Path, fresh_window_days: int, as_of: str) -> list[dict[str, Any]]:
    as_of_d = _dt.date.fromisoformat(as_of)
    out: list[dict[str, Any]] = []
    for md in sorted((Path(kb_dir) / "docs").glob("*.md")):
        text = md.read_text(encoding="utf-8")
        date_m = _DATE_RE.search(text)
        src_m = _SRC_RE.search(text)
        date = date_m.group(1) if date_m else None
        stale_flag = bool(_STALE_RE.search(text))
        fresh = False
        if date:
            age = (as_of_d - _dt.date.fromisoformat(date)).days
            fresh = age <= fresh_window_days
        for fm in _FINDING_RE.finditer(text):
            out.append({"content": fm.group(1).strip(),
                        "source_url": src_m.group(1) if src_m else None,
                        "date": date, "fresh": fresh and not stale_flag,
                        "stale": stale_flag or not fresh})
    return out


# ── gate checks (real BLOCK/WARN over the report body) ───────────────────────
def _report_body(dossier: dict[str, Any]) -> str:
    return dossier.get("report_md") or dossier.get("deliverable_body") or ""


def _gate_body_too_thin(dossier: dict[str, Any]) -> GateResult:
    body = _report_body(dossier)
    words = len(re.findall(r"\S+", body))
    ok = words >= BODY_MIN_WORDS
    return GateResult(gate="body_too_thin", severity=Severity.BLOCK, passed=ok, p0=not ok,
                      details=f"{words} words (floor {BODY_MIN_WORDS})", evidence={"words": words})


def _gate_footnote_orphan(dossier: dict[str, Any]) -> GateResult:
    body = _report_body(dossier)
    refs = {m.group(1) for m in _FN_REF_RE.finditer(body)}
    defs = {m.group(1) for m in _FN_DEF_RE.finditer(body)}
    orphan_refs = sorted(refs - defs)
    orphan_defs = sorted(defs - refs)
    ok = not orphan_refs and not orphan_defs
    return GateResult(gate="footnote_orphan", severity=Severity.BLOCK, passed=ok, p0=not ok,
                      details=f"orphan_refs={orphan_refs} orphan_defs={orphan_defs}",
                      evidence={"orphan_refs": orphan_refs, "orphan_defs": orphan_defs})


def _gate_uncited_quantitative(dossier: dict[str, Any]) -> GateResult:
    body = _report_body(dossier)
    uncited: list[str] = []
    for line in body.splitlines():
        for m in _NUM_RE.finditer(line):
            if "[^" not in line:   # the number's line carries no footnote
                uncited.append(m.group(0).strip())
    ok = not uncited
    return GateResult(gate="uncited_quantitative", severity=Severity.BLOCK, passed=ok, p0=not ok,
                      details=f"uncited numbers: {uncited}", evidence={"uncited_numbers": uncited})


def _gate_single_source(dossier: dict[str, Any]) -> GateResult:
    body = _report_body(dossier)
    sources = {m.group(2) for m in _FN_DEF_RE.finditer(body)}
    ok = len(sources) != 1
    return GateResult(gate="single_source_overreliance", severity=Severity.WARN, passed=ok,
                      details=f"distinct sources={len(sources)}",
                      evidence={"distinct_sources": len(sources)})


class InsurancePack(DomainPack):
    name = "insurance"

    def grill_schema(self) -> dict[str, Any]:
        return {
            "scope": {"prompt": "Report scope / topic", "type": "text"},
            "region": {"prompt": "Markets", "type": "multi",
                       "options": ["台灣", "日本", "韓國", "香港", "東南亞"]},
            "timeframe": {"prompt": "Timeframe", "type": "text"},
            "audience": {"prompt": "Audience", "type": "text"},
            "depth": {"prompt": "Depth", "type": "enum", "options": list(TIERS)},
        }

    def parse_contract(self, raw: dict[str, Any]) -> dict[str, Any]:
        c = dict(raw)
        c.setdefault("synthesis", {}).setdefault("scope", {})
        return c

    def data_sources(self) -> list[str]:
        return ["crawled_news_index", "monthly_wiki", "past_reports", "web_exa_ddg"]

    def viability_probe(self, contract: dict[str, Any], sources: dict[str, Any]) -> ViabilityVerdict:
        """target_findings yield from the KB sources (§2.2). Findings may be passed
        directly (sources['findings']) or extracted from a KB dir (sources['kb_dir'])."""
        findings = sources.get("findings")
        if findings is None and sources.get("kb_dir"):
            findings = _extract_findings_from_kb(
                Path(sources["kb_dir"]),
                int(sources.get("fresh_window_days", 120)),
                sources.get("as_of", "2026-06-15"))
        findings = findings or []
        n_total = len(findings)   # yield = findings the sources surface (tier driver)
        n_fresh = sum(1 for f in findings if f.get("fresh", not f.get("stale")))
        n_stale = n_total - n_fresh

        depth = ((contract.get("synthesis") or {}).get("scope") or {}).get("depth", "standard")
        tier_verdicts = {name: n_total >= need for name, need in TIERS.items()}
        target = TIERS.get(depth, TIERS["standard"])
        viable = n_total >= target

        pivots: list[str] = []
        if not viable:
            ok_tiers = [t for t, v in tier_verdicts.items() if v]
            pivots = ([f"narrow to a viable depth: {ok_tiers[-1]}"] if ok_tiers else
                      ["widen the region set or timeframe to surface more findings"])
        return ViabilityVerdict(
            viable=viable,
            reason=f"{n_total} findings ({n_fresh} fresh, {n_stale} stale) vs target "
                   f"{target} ({depth}); viable tiers: {[t for t, v in tier_verdicts.items() if v]}",
            metric={"total_findings": n_total, "fresh_findings": n_fresh,
                    "stale_findings": n_stale, "target": target},
            candidate_pivots=pivots, contract_hash=self.contract_hash(contract),
            tier_verdicts=tier_verdicts)

    def section_template(self) -> list[str]:
        return ["市場概況", "競品動態", "觀察洞察", "歷史對照", "策略建議", "風險限制", "參考資料"]

    def gate_registry(self) -> list[Gate]:
        return [
            Gate("body_too_thin", Severity.BLOCK, _gate_body_too_thin, when="before deliver"),
            Gate("footnote_orphan", Severity.BLOCK, _gate_footnote_orphan, when="before deliver"),
            Gate("uncited_quantitative", Severity.BLOCK, _gate_uncited_quantitative, when="before deliver"),
            Gate("single_source_overreliance", Severity.WARN, _gate_single_source, when="before deliver"),
        ]

    def review_rubric(self) -> dict[str, Any]:
        return {
            "findings": {"every_finding_has_source_url": True, "conflicts_flagged": True},
            "freshness": {"stale_sources_flagged": True},
            "sources": {"min_distinct": 2},
        }

    def render(self, dossier: dict[str, Any], out_dir: Path) -> dict[str, Any]:
        # Deliverable = markdown -> DOCX (no PDF).
        return {"deliverable": "docx", "docx": str(Path(out_dir) / "report.docx")}
