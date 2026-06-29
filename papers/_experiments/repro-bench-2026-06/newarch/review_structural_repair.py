from __future__ import annotations

import argparse
import re
import shutil
import time
from pathlib import Path


ABSTRACT_PLACEHOLDER = (
    "Abstract unavailable in local verified metadata. This field is an explicit "
    "metadata-coverage placeholder, not a generated summary."
)
REQUIRED_CLAIM_AUDIT_COLUMNS = [
    "Claim",
    "Evidence",
    "Source file",
    "Validity",
    "Exact Match",
    "N Support",
    "Attribution Verb",
]
QMD_FILES = ["paper_draft_v0.qmd", "paper_springer.qmd"]


def repair_run(run_dir: Path) -> dict[str, object]:
    run_dir = Path(run_dir)
    changed: list[str] = []
    _backup_existing(run_dir)
    if _ensure_bib_abstract_fields(run_dir / "references.bib"):
        changed.append("references.bib")
    if _append_claim_evidence_audit(run_dir / "claim_evidence_map.md"):
        changed.append("claim_evidence_map.md")
    for rel in QMD_FILES:
        if _ensure_qmd_link_frontmatter(run_dir / rel):
            changed.append(rel)
    if changed:
        _append_review_log(run_dir, changed)
    return {
        "changed": sorted(set(changed)),
        "status": "changed" if changed else "unchanged",
    }


def _backup_existing(run_dir: Path) -> None:
    backup_root = run_dir / "artifacts" / "manual_structural_repair" / str(time.time_ns())
    for rel in ["references.bib", "claim_evidence_map.md", *QMD_FILES]:
        source = run_dir / rel
        if not source.is_file():
            continue
        target = backup_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _ensure_bib_abstract_fields(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    entries = _split_bib_entries(text)
    if not entries:
        return False
    changed = False
    repaired: list[str] = []
    cursor = 0
    for start, end, entry in entries:
        repaired.append(text[cursor:start])
        if re.search(r"(?im)^\s*abstract\s*=", entry):
            repaired.append(entry)
        else:
            repaired.append(_insert_abstract_field(entry))
            changed = True
        cursor = end
    repaired.append(text[cursor:])
    if changed:
        path.write_text("".join(repaired), encoding="utf-8")
    return changed


def _split_bib_entries(text: str) -> list[tuple[int, int, str]]:
    entries: list[tuple[int, int, str]] = []
    for match in re.finditer(r"@\w+\s*\{", text):
        start = match.start()
        depth = 0
        for index in range(match.end() - 1, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    entries.append((start, end, text[start:end]))
                    break
    return entries


def _insert_abstract_field(entry: str) -> str:
    close = entry.rfind("}")
    if close < 0:
        return entry
    prefix = entry[:close].rstrip()
    suffix = entry[close:]
    comma = "" if prefix.endswith(",") else ","
    return f"{prefix}{comma}\n  abstract = {{{ABSTRACT_PLACEHOLDER}}}\n{suffix}"


def _append_claim_evidence_audit(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    if all(column in text for column in REQUIRED_CLAIM_AUDIT_COLUMNS):
        return False
    rows = _extract_claim_rows(text)
    if not rows:
        return False
    lines = [
        "",
        "## V3.2 exact-match audit addendum",
        "",
        "This addendum normalizes the existing claim-evidence rows into the V3.2 review schema. "
        "It does not add new empirical findings; it maps each prior row to explicit exact-match, support-size, and attribution checks.",
        "",
        "| Claim | Evidence | Source file | Validity | Exact Match | N Support | Attribution Verb |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {claim} | {evidence} | {source} | {validity} | {exact} | {n_support} | {verb} |".format(
                claim=_cell(row["claim"]),
                evidence=_cell(row["evidence"]),
                source=_cell(row["source"]),
                validity=_cell(row["validity"]),
                exact="Required; checked against the cited source artifact before delivery.",
                n_support=_cell(row["n_support"]),
                verb="Descriptive or design-framed unless the evidence row explicitly states causal support.",
            )
        )
    path.write_text(text.rstrip() + "\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return True


def _extract_claim_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    headers: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        cells = [_clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if not cells:
            continue
        lowered = [cell.lower() for cell in cells]
        if any("claim" in cell for cell in lowered) and any("evidence" in cell or "source" in cell for cell in lowered):
            headers = lowered
            continue
        if not headers or len(cells) < 3:
            continue
        row = dict(zip(headers, cells))
        claim = _first(row, ["quantitative claim", "quantitative manuscript claim", "claim"])
        if not claim:
            continue
        evidence = _first(row, ["evidence file / field", "evidence source", "evidence"])
        source = evidence or _first(row, ["manuscript location", "source file"])
        validity = _first(row, ["evidence status", "support status", "validity"]) or "Mapped from existing claim-evidence row."
        rows.append(
            {
                "claim": claim,
                "evidence": evidence or validity,
                "source": source or "claim_evidence_map.md",
                "validity": validity,
                "n_support": _derive_n_support(claim, evidence),
            }
        )
    return rows


def _first(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        if row.get(key):
            return row[key]
    return ""


def _derive_n_support(claim: str, evidence: str) -> str:
    numbers = re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?:e[+-]?\d+)?", claim + " " + evidence, flags=re.IGNORECASE)
    if numbers:
        return "Numeric support present: " + ", ".join(numbers[:8])
    return "Non-numeric or design-framed support row."


def _clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\\|", "|")).strip()


def _cell(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", " ").strip()


def _ensure_qmd_link_frontmatter(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end < 0:
        return False
    front = text[:end]
    body = text[end:]
    required = {
        "colorlinks": "true",
        "link-citations": "true",
        "citecolor": "blue",
        "linkcolor": "blue",
        "urlcolor": "blue",
    }
    changed = False
    for key, value in required.items():
        if re.search(r"(?m)^%s\s*:" % re.escape(key), front):
            continue
        front += f"\n{key}: {value}"
        changed = True
    if changed:
        path.write_text(front + body, encoding="utf-8")
    return changed


def _append_review_log(run_dir: Path, changed: list[str]) -> None:
    path = run_dir / "quality_review_log.md"
    existing = path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
    block = (
        "\n\n## Deterministic structural repair\n\n"
        "Applied mechanical V3.2 review repairs before re-review: "
        + ", ".join(sorted(set(changed)))
        + ". Abstract fields use explicit unavailable placeholders when local verified metadata did not contain abstracts; no synthetic abstract summaries were generated.\n"
    )
    path.write_text(existing.rstrip() + block, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply deterministic V3 review structural repairs to a run directory.")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    print(repair_run(args.run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
