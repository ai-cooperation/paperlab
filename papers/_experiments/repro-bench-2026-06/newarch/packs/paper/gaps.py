"""Parse the research-gap matrix out of the brain's phase-3 markdown.

Shared so the PIPELINE stores STRUCTURED gaps in the dossier at phase-gap time (the
robust path — the projection then reads a structured field, not markdown), AND the HTTP
projection can still fall back to parsing the file for OLD runs whose dossier predates
this. Standalone (only `re`) so neither importer pulls heavy deps.

GENERAL by design: matches ANY table whose first header is a Gap alias (en/zh), not a
fixed English heading or a fixed column order.
"""
from __future__ import annotations

import re

# a gap table's first header may be localized — recognise these (en + zh)
_GAP_HEADER_ALIASES = ("gap", "缺口", "研究缺口", "研究空白", "空白")
_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}")          # a |---|---| markdown separator row


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_gap_matrix(text: str, limit: int = 5) -> list[dict[str, str]]:
    """Return [{gap, description}] from the first markdown table whose first column header
    is a Gap alias. Empty list if none — never raises."""
    if not text:
        return []
    lines = text.splitlines()
    out: list[dict[str, str]] = []
    for i, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("|"):
            continue
        header = [c.lower() for c in _cells(s)]
        if not header or not any(header[0].startswith(a) for a in _GAP_HEADER_ALIASES):
            continue
        # header found; rows follow the separator line
        start = i + 2 if (i + 1 < len(lines) and _SEP_RE.match(lines[i + 1])) else i + 1
        for row in lines[start:]:
            r = row.strip()
            if not r.startswith("|"):
                break
            cells = _cells(r)
            label = cells[0] if cells else ""
            if not label or not (set(label) - set("-: ")):   # skip blank / separator-ish rows
                continue
            out.append({"gap": label, "description": cells[1] if len(cells) > 1 else ""})
            if len(out) >= limit:
                break
        break
    return out
