"""Presentation-precision formatter for a delivered qmd. Rounds raw-float artifacts to
academic display precision in BOTH markdown tables (column-aware: p-value columns get
p</=, other columns 3 significant figures) and prose (>=5-decimal artifacts + p-values).

WHY: the general dataset lane's tables are writer-authored from metrics_block (the
deterministic table generator returns [] for it), so the agent transcribes raw 16-decimal
floats (`3.6285577215297318`, `p = 1.149e-83`). This single idempotent pass rounds them.

SAFETY: only DECIMAL floats are touched — bare integers (years 2000, counts 4406, n 1102)
have no '.' and are never matched. In prose a legit short decimal (a DOI's 10.1007, a
version) has <=4 decimals and is never matched (artifacts are >=5). Runs in
`_phase_format_repair` AFTER number_trace (phase render_gates), so the academic "<0.001"
wording cannot trip the traceability gate. Owns ONE fact: display precision. Idempotent.
"""
from __future__ import annotations

import math
import re

# DECIMAL floats only (optionally scientific). Bare integers carry no '.', so years/counts
# are never matched.
_NUM = re.compile(r"-?\d+\.\d+(?:[eE][+-]?\d+)?")
_SEP = re.compile(r"^\s*\|[\s:|-]+\|?\s*$")
# PROSE artifact: >=5 decimals (a legit short decimal — DOI 10.1007, a ratio — has <=4).
_PROSE_NUM = re.compile(r"-?\d+\.\d{5,}(?:[eE][+-]?\d+)?")
_PROSE_P = re.compile(r"\bp\s*([=<])\s*(-?\d+\.\d+(?:[eE][+-]?\d+)?)")


def _fmt_num(x: float) -> str:
    a = abs(x)
    if a == 0:
        return "0"
    if a >= 1000:
        return f"{x:.0f}"
    if a >= 1:
        return f"{x:.2f}"
    dec = min(max(2 - int(math.floor(math.log10(a))), 3), 6)   # ~3 significant figures
    return f"{x:.{dec}f}"


def _fmt_p(x: float) -> str:
    return "<0.001" if x < 0.001 else f"{x:.3f}"


def _is_p_col(header: str) -> bool:
    h = header.strip().lower()
    return h == "p" or h == "p val" or "p-value" in h or "p value" in h


def _format_row(row: str, p_cols: set[int]) -> str:
    parts = row.split("|")              # parts[0] before first |, parts[-1] after last |
    for idx in range(1, len(parts) - 1):
        fmt = _fmt_p if (idx - 1) in p_cols else _fmt_num

        def _sub(m: "re.Match[str]", _fmt=fmt) -> str:
            try:
                return _fmt(float(m.group(0)))
            except ValueError:
                return m.group(0)

        parts[idx] = _NUM.sub(_sub, parts[idx])
    return "|".join(parts)


def _format_prose_line(line: str) -> str:
    def _p_sub(m: "re.Match[str]") -> str:
        try:
            val = _fmt_p(float(m.group(2)))
        except ValueError:
            return m.group(0)
        return "p < 0.001" if val == "<0.001" else f"p {m.group(1)} {val}"

    def _n_sub(m: "re.Match[str]") -> str:
        try:
            return _fmt_num(float(m.group(0)))
        except ValueError:
            return m.group(0)

    return _PROSE_NUM.sub(_n_sub, _PROSE_P.sub(_p_sub, line))


def format_numbers(text: str) -> str:
    """Round float artifacts to display precision in tables and prose. Idempotent."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("|") and i + 1 < len(lines) and _SEP.match(lines[i + 1]):
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            p_cols = {idx for idx, h in enumerate(header_cells) if _is_p_col(h)}
            out.append(line)                # header unchanged
            out.append(lines[i + 1])        # separator unchanged
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                out.append(_format_row(lines[i], p_cols))
                i += 1
            continue
        out.append(_format_prose_line(line))
        i += 1
    return "\n".join(out)


def format_qmd(qmd_path) -> bool:
    """Apply format_numbers to a qmd file in place. Returns True if it changed."""
    from pathlib import Path
    p = Path(qmd_path)
    if not p.is_file():
        return False
    src = p.read_text(encoding="utf-8", errors="ignore")
    out = format_numbers(src)
    if out != src:
        p.write_text(out, encoding="utf-8")
    return out != src
