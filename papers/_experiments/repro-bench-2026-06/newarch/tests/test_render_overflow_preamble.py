"""Lock the deterministic Overfull-\\hbox prevention wired into the springer
preamble.

Root cause (job v3_6cc4fe4d1922, carbon-tax): a 7-column longtable header cell
overflowed its narrow p{} column by ~15.4pt under \\footnotesize. The document-
global \\emergencystretch pandoc injects could NOT absorb it — a single oversized
header cell has no interword glue to stretch — so the overflow reached Gate Z,
which blocks the render. format_repair is a 0-round stage by design, so a fresh
job could only escape via the auto-retry timer re-running review_heal to reword
the table (luck), never a deterministic fix.

The fix is purely mechanical (typesetting), so it lives in the renderer, not a
model repair round: inside the longtable environment (scope auto-reverts on
\\end{longtable}) drop the font to \\scriptsize, enable \\sloppy, and re-arm
\\emergencystretch. These tests assert the mechanism EXISTS and is correctly
scoped so it can never silently regress out of the preamble.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import render_springer

pytestmark = pytest.mark.unit


def _preamble(tmp_path: Path) -> str:
    """Normalise a minimal qmd and return the include-in-header preamble text."""
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "---\n"
        'title: "Overfull Prevention Paper"\n'
        "abstract: |\n"
        "  A short abstract about wide seven-column result tables.\n"
        "keywords:\n"
        "  - reproducible benchmark\n"
        "  - wide tables\n"
        "  - carbon tax\n"
        "bibliography: references.bib\n"
        "---\n\n"
        "# Introduction\n\nBody text with @tbl-main-estimates.\n",
        encoding="utf-8",
    )
    out = render_springer.normalize_frontmatter(
        tmp_path, {}, out_name="paper_springer.qmd"
    )
    text = out.read_text(encoding="utf-8")
    # Grab the include-in-header text block (indented under `text: |`).
    m = re.search(r"(?ms)^    include-in-header:\n      text: \|\n(.*?)^csl:", text)
    assert m, "include-in-header text block not found in normalised frontmatter"
    return m.group(1)


def test_longtable_hook_carries_scriptsize_sloppy_and_emergencystretch(tmp_path):
    preamble = _preamble(tmp_path)
    # The longtable AtBeginEnvironment hook must exist and carry all three
    # levers on the SAME line so they are scoped to the longtable environment.
    m = re.search(r"\\AtBeginEnvironment\{longtable\}\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", preamble)
    assert m, "no \\AtBeginEnvironment{longtable}{...} hook in preamble"
    hook = m.group(0)
    assert "\\scriptsize" in hook, "longtable hook must drop font to \\scriptsize"
    assert "\\sloppy" in hook, "longtable hook must enable \\sloppy"
    assert "\\emergencystretch" in hook, "longtable hook must re-arm \\emergencystretch"


def test_emergencystretch_and_sloppy_are_scoped_not_global(tmp_path):
    """\\sloppy / \\emergencystretch must appear ONLY inside AtBeginEnvironment
    hooks, never as bare document-global commands (a global \\sloppy would loosen
    every body paragraph's spacing)."""
    preamble = _preamble(tmp_path)
    for line in preamble.splitlines():
        stripped = line.strip()
        if stripped.startswith("%"):
            continue  # LaTeX comment lines may mention the levers in prose
        if "\\sloppy" in stripped or "\\emergencystretch" in stripped:
            assert stripped.startswith("\\AtBeginEnvironment{"), (
                f"typesetting lever must be scoped to an environment, got: {stripped!r}"
            )


def test_etoolbox_loaded_for_atbeginenvironment(tmp_path):
    """\\AtBeginEnvironment is provided by etoolbox; without it the hooks fail."""
    preamble = _preamble(tmp_path)
    assert "\\usepackage{etoolbox}" in preamble, "etoolbox must be loaded"
    # etoolbox must be loaded BEFORE the first \AtBeginEnvironment use.
    etoolbox_at = preamble.index("\\usepackage{etoolbox}")
    first_hook_at = preamble.index("\\AtBeginEnvironment{")
    assert etoolbox_at < first_hook_at, "etoolbox must load before AtBeginEnvironment"


def test_xurl_loaded_defensively_for_url_class_overflow(tmp_path):
    """Long DOIs/URLs are the other Overfull class; xurl adds URL break points.
    It must load via \\IfFileExists so a xurl-less TeX install cannot hard-fail
    the render (mirrors pandoc's own guard)."""
    preamble = _preamble(tmp_path)
    assert "xurl" in preamble, "xurl should be loaded for URL line breaking"
    assert "\\IfFileExists{xurl.sty}{\\usepackage{xurl}}{}" in preamble, (
        "xurl must load defensively via \\IfFileExists, not an unconditional \\usepackage"
    )


def test_tabular_hook_also_hardened(tmp_path):
    """The narrower tabular environment keeps \\footnotesize but also gets
    \\sloppy + \\emergencystretch so it cannot become a silent overflow source."""
    preamble = _preamble(tmp_path)
    m = re.search(r"\\AtBeginEnvironment\{tabular\}\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", preamble)
    assert m, "no \\AtBeginEnvironment{tabular}{...} hook in preamble"
    hook = m.group(0)
    assert "\\sloppy" in hook and "\\emergencystretch" in hook
