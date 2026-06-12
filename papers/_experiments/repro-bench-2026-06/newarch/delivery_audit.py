#!/usr/bin/env python3
"""Pre-delivery audit — the systematized filter layer.

Every defect a human reviewer caught in a pipeline deliverable (and that the
automated gates had missed) becomes a mechanical check here, so the NEXT paper
never ships it. This is the staging ground: a check proven here migrates into a
by-construction gate upstream, but the audit is the single go/no-go run before a
paper is called a deliverable. Pairs with the ~/.claude/skills/paper-delivery-audit
failure-case library (the human-readable case index).

It consolidates the existing render-quality gates (revision_tasks.RQ_*) and adds
the classes that previously only human review caught:
  D1 refs-count           — meta-analysis shipped with 4 references (too few)
  D2 promise-vs-capability — title/abstract claims a method the engine never ran
                             (Bayesian LCA, network MA, meta-regression, ...)
  D3 subgroup-promise-gap  — proposal promised "subgroup by X" but no subgroup ran
  D4 synthesis-type-match  — contract synthesis.type != delivered synthesis_type

No LLM. Pure inspection of the run_dir artifacts. Returns issues + a verdict.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Methods the automated engine does NOT run (mirror of capabilities.not_supported);
# if any appears in the title/abstract as if performed, that is a promise mismatch.
UNSUPPORTED_METHOD_PATTERNS = [
    r"bayesian", r"latent[ -]?class", r"network meta", r"meta[ -]?regression",
    r"individual[ -]patient[ -]data", r"\bIPD\b", r"\bRoB ?2\b", r"\bGRADE\b",
    r"trim[ -]and[ -]fill",
]
MIN_REFS_META = 20   # a meta-analysis cites far more than its included studies


def _read_json(p: Path, default: Any) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
    except (json.JSONDecodeError, OSError):
        return default


def _read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore") if p.is_file() else ""
    except OSError:
        return ""


def _issue(cid: str, sev: str, msg: str, **extra: Any) -> dict[str, Any]:
    return {"id": cid, "severity": sev, "type": "delivery_audit", "message": msg, **extra}


def _refs_count_check(run_dir: Path, rr: dict[str, Any]) -> list[dict[str, Any]]:
    if str(rr.get("lane") or "") not in ("meta_analysis", "scientometric"):
        return []
    bib = _read_text(run_dir / "references.bib")
    n = len(re.findall(r"^@\w+\s*\{", bib, re.M))
    if n < MIN_REFS_META:
        return [_issue("D1_REFS_TOO_FEW", "P0",
                       f"meta-analysis shipped with only {n} references (need >= {MIN_REFS_META}); "
                       "expand_references likely failed", count=n)]
    return []


def _promise_capability_check(run_dir: Path) -> list[dict[str, Any]]:
    qmd = _read_text(run_dir / "paper_draft_v0.qmd")
    if not qmd:
        return []
    # only inspect the framing (title + abstract + first heading block), where an
    # over-claim does damage; a method named once in Future Work is fine.
    head = qmd[:2500].lower()
    fut = qmd.lower().find("future work")
    hits = [p for p in UNSUPPORTED_METHOD_PATTERNS
            if (m := re.search(p, head)) and (fut == -1 or m.start() < fut)]
    if hits:
        return [_issue("D2_PROMISE_MISMATCH", "P0",
                       "title/abstract claims a method the automated engine never ran "
                       f"({', '.join(hits)}); a should have rewritten it to DerSimonian-Laird",
                       methods=hits)]
    return []


def _subgroup_promise_check(run_dir: Path, rr: dict[str, Any]) -> list[dict[str, Any]]:
    qmd = _read_text(run_dir / "paper_draft_v0.qmd").lower()
    promises_subgroup = "subgroup" in qmd
    sens = (rr.get("meta") or {}).get("sensitivity") or {}
    ran_subgroup = any(k.startswith("subgroup") for k in sens)
    if promises_subgroup and not ran_subgroup and str(rr.get("lane") or "") == "meta_analysis":
        return [_issue("D3_SUBGROUP_GAP", "P1",
                       "paper discusses a subgroup analysis but real_results ran none "
                       "(effects carry no moderator tag); the promised subgroup did not compute")]
    return []


def _reference_quality_check(run_dir: Path) -> list[dict[str, Any]]:
    """Catch the reference/citation garble a human reviewer spots instantly:
    author-less bib entries (render as ', 1978. Title' and cite as the raw key
    'ref (1978)'), and the 'Table Table 1' / 'Figure Figure 2' double prefix."""
    out: list[dict[str, Any]] = []
    bib = _read_text(run_dir / "references.bib")
    entries = re.split(r"(?=^@\w+\s*\{)", bib, flags=re.M)
    noauthor = [e for e in entries if e.strip().startswith("@")
                and not re.search(r"^\s*author\s*=", e, re.M | re.I)]
    if noauthor:
        out.append(_issue("D5_REF_NO_AUTHOR", "P0",
                          f"{len(noauthor)} reference(s) have no author (render as ', YEAR. Title' "
                          "and cite as the raw bibkey); drop them in expand_references",
                          count=len(noauthor)))
    qmd = _read_text(run_dir / "paper_draft_v0.qmd")
    if re.search(r"\bref\s*\(\s*(?:19|20)\d\d", qmd) or re.search(r"@ref\d{4}\b", qmd):
        out.append(_issue("D5_CITE_BIBKEY", "P0",
                          "in-text citation shows a raw bibkey (e.g. 'ref (1978)') — an "
                          "author-less reference was cited"))
    if re.search(r"\b(Table\s+Table|Figure\s+Figure)\b", qmd):
        out.append(_issue("D5_DOUBLE_PREFIX", "P1",
                          "'Table Table' / 'Figure Figure' double prefix (writer wrote "
                          "'Table @tbl-x'; Quarto adds its own 'Table')"))
    return out


def _synthesis_type_check(run_dir: Path, rr: dict[str, Any]) -> list[dict[str, Any]]:
    contract = _read_json(run_dir.parent / "contract.json", {})
    want = str(((contract.get("synthesis") or {}).get("type") or "")).lower()
    got = str(rr.get("synthesis_type") or "").lower()
    if want and got and want != got:
        return [_issue("D4_SYNTHESIS_MISMATCH", "P0",
                       f"contract asked synthesis.type='{want}' but engine delivered '{got}'",
                       wanted=want, got=got)]
    return []


def audit(run_dir: Path) -> dict[str, Any]:
    """Run the full pre-delivery audit. Returns {verdict, issues, summary}."""
    run_dir = Path(run_dir)
    rr = _read_json(run_dir / "real_experiments" / "real_results.json", {})

    issues: list[dict[str, Any]] = []
    # consolidate the existing render-quality gates
    try:
        import revision_tasks
        issues.extend(revision_tasks.render_quality_check(run_dir))
    except Exception as exc:  # noqa: BLE001 - audit must not crash the run
        issues.append(_issue("AUDIT_RQ_ERROR", "P1", f"render_quality_check failed: {exc}"))
    # add the human-caught classes
    issues.extend(_refs_count_check(run_dir, rr))
    issues.extend(_promise_capability_check(run_dir))
    issues.extend(_subgroup_promise_check(run_dir, rr))
    issues.extend(_synthesis_type_check(run_dir, rr))
    issues.extend(_reference_quality_check(run_dir))

    p0 = [i for i in issues if i.get("severity") == "P0"]
    p1 = [i for i in issues if i.get("severity") == "P1"]
    verdict = "blocked" if p0 else ("warn" if p1 else "pass")
    result = {
        "verdict": verdict,
        "p0_count": len(p0), "p1_count": len(p1),
        "issues": issues,
        "summary": f"{verdict.upper()} — {len(p0)} P0, {len(p1)} P1",
    }
    (run_dir / "delivery_audit.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result


if __name__ == "__main__":
    import sys
    r = audit(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    print(r["summary"])
    for i in r["issues"]:
        detail = i.get("message") or i.get("detail") or i.get("type") or ""
        print(f"  [{i.get('severity')}] {i.get('id')}: {str(detail)[:100]}")
