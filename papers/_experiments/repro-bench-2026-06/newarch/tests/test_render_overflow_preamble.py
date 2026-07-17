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

Second root cause (job v3_72f87c735de5, tablet paper): the 7-column longtable's
NARROWEST p{} cells are only ~0.4in wide, and several cells carry long slash-
joined tokens (abstract/metadata, Subject/outcome, Crossref/OpenAlex,
Difference-in-differences/event). LaTeX treats each as a single UNBREAKABLE box
because '/' is not a legal break point, so \\scriptsize/\\sloppy/\\emergencystretch
(which need interword glue or an in-word hyphen break) could not help — 11 visible
Overfull \\hbox (~17.2pt) reached Gate Z. The deterministic fix makes '/' an
active-catcode break opportunity that prints a REAL slash (\\string/, so the glyph
is never dropped — \\char / \\slash / \\discretionary all silently ate the slash in
live testing) followed by \\penalty0. It is armed by \\PLbreakslashes ONLY inside
the longtable/tabular hooks, so body prose and reference-list URLs keep their
literal slashes. Live-verified on job v3_72f87c735de5 via the real render() path:
Gate Z Overfull 11 -> 0 (log total 17 -> 0), all slashes preserved in the PDF.
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
    """\\sloppy / \\emergencystretch must appear ONLY inside a scoping construct,
    never as a bare document-global command (a global \\sloppy would loosen every
    body paragraph's spacing). Two legal scopes exist:
      - table environments via \\AtBeginEnvironment{...} (slash-break class), and
      - the redefined \\texttt via \\renewcommand{\\texttt}... (prose-texttt
        class): \\emergencystretch is set INSIDE \\texttt so it is read at the
        enclosing \\par and thus applies to ONLY paragraphs that contain a
        \\texttt (texttt-free prose keeps tight justification). \\sloppy must
        still never leak: it is NOT used in the texttt path."""
    preamble = _preamble(tmp_path)
    for line in preamble.splitlines():
        stripped = line.strip()
        if stripped.startswith("%"):
            continue  # LaTeX comment lines may mention the levers in prose
        # \sloppy is only ever legal inside a table hook.
        if "\\sloppy" in stripped:
            assert stripped.startswith("\\AtBeginEnvironment{"), (
                f"\\sloppy must be scoped to a table environment, got: {stripped!r}"
            )
        # \emergencystretch is legal inside a table hook OR inside the \texttt
        # redefinition (paragraph-scoped to texttt-bearing paragraphs only).
        if "\\emergencystretch" in stripped:
            assert stripped.startswith("\\AtBeginEnvironment{") or stripped.startswith(
                "\\renewcommand{\\texttt}"
            ), (
                "\\emergencystretch must be scoped to a table hook or the \\texttt "
                f"redefinition, never bare document-global, got: {stripped!r}"
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


# --- slash-break class (job v3_72f87c735de5, tablet paper) -------------------
# The 17.2pt Overfull came from long slash-joined tokens in ~0.4in-wide cells
# that font/glue levers cannot touch. The deterministic fix makes '/' a break
# opportunity, armed by \PLbreakslashes ONLY inside the table hooks.


def test_slashbreak_helper_defined(tmp_path):
    """A \\PLbreakslashes command must exist and turn '/' into an active-catcode
    break point. Without it the narrow slash-joined cells overflow by ~17pt."""
    preamble = _preamble(tmp_path)
    assert "\\newcommand{\\PLbreakslashes}" in preamble, (
        "preamble must define the \\PLbreakslashes slash-break helper"
    )
    # It must flip '/' to an active char (catcode 13) — that is what creates the
    # break opportunity a plain \sloppy/\emergencystretch cannot.
    assert "\\catcode`\\/=13" in preamble, (
        "\\PLbreakslashes must make '/' an active character (catcode 13)"
    )


def test_slashbreak_prints_a_real_slash_via_string(tmp_path):
    """The active '/' must expand to a REAL catcode-12 slash via \\string/ so the
    glyph is NEVER dropped. \\char / \\slash / \\discretionary all silently ate
    the slash in live testing; only \\string/ preserved it in the rendered PDF."""
    preamble = _preamble(tmp_path)
    assert "\\string/\\penalty0" in preamble, (
        "active '/' must emit \\string/ (a real slash) then a neutral \\penalty0 break; "
        "\\char/\\slash/\\discretionary drop the slash in the PDF"
    )


def test_slashbreak_armed_only_inside_table_hooks(tmp_path):
    """\\PLbreakslashes must be invoked inside BOTH the longtable and tabular
    AtBeginEnvironment hooks — and nowhere as a bare document-global command, so
    body prose and reference-list URLs keep their literal slashes."""
    preamble = _preamble(tmp_path)
    # Each AtBeginEnvironment hook is one preamble line; match to end-of-line so
    # the nested \setlength{...}{...} braces don't truncate the captured body.
    for env in ("longtable", "tabular"):
        m = re.search(
            r"^\s*\\AtBeginEnvironment\{" + env + r"\}\{.*$",
            preamble,
            re.MULTILINE,
        )
        assert m, f"no \\AtBeginEnvironment{{{env}}}{{...}} hook in preamble"
        assert "\\PLbreakslashes" in m.group(0), (
            f"{env} hook must arm \\PLbreakslashes so its slash cells can wrap"
        )
    # \PLbreakslashes must never be called bare (outside a hook / its own def),
    # which would leak the active catcode into body prose and DOI URLs.
    for line in preamble.splitlines():
        stripped = line.strip()
        if stripped.startswith("%"):
            continue
        if "\\PLbreakslashes" not in stripped:
            continue
        assert stripped.startswith("\\AtBeginEnvironment{") or stripped.startswith(
            "\\newcommand{\\PLbreakslashes}"
        ), f"\\PLbreakslashes must only appear in a table hook or its definition, got: {stripped!r}"


# --- prose \texttt break class (job v3_4dc73d199e17, accounting) --------------
# A THIRD Overfull class, distinct from both table classes above: long \texttt{}
# INLINE CODE in body PROSE. On job v3_4dc73d199e17 the tokens
#   \texttt{real\_experiments/real\_results.json}
#   \texttt{analysis\_type\ =\ deterministic\_reference\_evidence\_map}
# were single unbreakable boxes overflowing by 8.44pt and 49.53pt (>=5pt each ->
# 2 Gate Z blocks). The table-scoped \PLbreakslashes never fires in prose, so the
# slash-break fix could not reach them.
#
# FAKE-SOLUTION LOG (each tried live on the real render, each failed):
#   1. hyphenat[htt] / seqsplit          -> no break point at snake_case '_' or '='.
#   2. active-catcode _ . = / document-wide -> the active '.' broke \hsize=1.2in
#      dimension parsing and math; too invasive for prose.
#   3. \str_map_inline over the argument -> STRINGIFIES the pandoc \_ and \ escapes
#      into literal backslashes -> rendered "real\_experiments" (glyph corrupted).
#   4. \discretionary{}{}{} / \- / \penalty0 breakpoints WITHOUT tolerance -> TeX
#      refuses the break (no interword glue -> infinite badness on the short line);
#      still overflowed. Breakpoints are inert alone.
#   5. \begingroup...\endgroup around \setlength{\emergencystretch} inside \texttt
#      -> reverts emergencystretch before the \par reads it -> overflow WORSENED
#      to 70pt.
#   6. \PLttbreak:n called from \renewcommand{\texttt} under \ExplSyntaxOff ->
#      ':' is catcode-12 there, so ':n' leaked as literal glyphs into the PDF
#      (":nreal_experiments..."). Must expose an l3 fn via \NewDocumentCommand.
#
# WINNING MECHANISM (live-verified: Gate Z 2 -> 0, log total 3 -> 0, 15pp PDF
# unchanged, every glyph intact via pdftotext whitespace-stripped compare):
#   - \tl_map_inline (TOKEN list, preserves \_ / \ control seqs) re-emits each
#     token UNTOUCHED then appends \penalty0 after break-worthy tokens (\_ / . =).
#     Glyph-faithful by construction (original char emitted first, never replaced).
#   - \emergencystretch set INSIDE the redefined \texttt (read at the enclosing
#     \par) supplies the tolerance so the breakpoints are actually taken, scoped
#     to texttt-bearing paragraphs only (no global prose loosening).


def test_prose_texttt_break_helper_defined(tmp_path):
    """The prose-\\texttt fix must define an expl3 token-list walker and expose it
    via a \\NewDocumentCommand wrapper so it is callable in normal catcodes (a raw
    \\pl_ttbreak:n call under \\ExplSyntaxOff leaked ':n' glyphs into the PDF)."""
    preamble = _preamble(tmp_path)
    assert "\\cs_new_protected:Npn \\pl_ttbreak:n" in preamble, (
        "preamble must define the expl3 token-list break walker \\pl_ttbreak:n"
    )
    assert "\\NewDocumentCommand{\\PLttbreak}{m}{\\pl_ttbreak:n{#1}}" in preamble, (
        "\\pl_ttbreak:n must be exposed via a \\NewDocumentCommand wrapper so the "
        "':' in its l3 name is not parsed as text when \\texttt calls it"
    )


def _code_lines(preamble: str) -> str:
    """Preamble with LaTeX comment lines stripped — assertions about the ACTUAL
    mechanism must not trip over rejected alternatives named in the prose comments
    (the slash-break comment legitimately mentions \\discretionary/\\slash/\\str)."""
    return "\n".join(
        ln for ln in preamble.splitlines() if not ln.strip().startswith("%")
    )


def test_prose_texttt_walks_token_list_not_string(tmp_path):
    """It must use \\tl_map_inline (token list), NOT \\str_map: \\str_map would
    stringify pandoc's \\_ / \\  escapes into literal backslashes and corrupt the
    glyph. The escaped underscore is matched as a control sequence via \\tl_if_eq."""
    preamble = _preamble(tmp_path)
    code = _code_lines(preamble)
    assert "\\tl_map_inline:nn" in code, (
        "must walk the argument as a token list (\\tl_map_inline), never \\str_map"
    )
    assert "\\str_map" not in code, (
        "\\str_map stringifies the pandoc \\_/\\  escapes -> corrupts the glyph"
    )
    # The escaped underscore is a control sequence -> matched with \tl_if_eq, the
    # literal punctuation with \str_if_eq.
    assert "\\tl_if_eq:nnT {##1} {\\_}" in preamble, (
        "escaped underscore \\_ must be matched as a control seq via \\tl_if_eq"
    )
    for ch in ("/", ".", "="):
        assert "\\str_if_eq:nnT {##1} {%s}" % ch in preamble, (
            f"break-worthy char {ch!r} must add a \\penalty0"
        )


def test_prose_texttt_preserves_glyph_by_reemitting_original_token(tmp_path):
    """Glyph safety is by CONSTRUCTION: the loop emits the original token (##1)
    FIRST, then only appends a neutral \\penalty0 — it never replaces the char
    with \\char/\\slash/\\discretionary (all of which dropped glyphs in testing)."""
    preamble = _preamble(tmp_path)
    code = _code_lines(preamble)
    m = re.search(r"\\tl_map_inline:nn \{#1\} \{\s*##1", code)
    assert m, "the token-map body must emit the original token ##1 before any penalty"
    # The break is a bare \penalty0 (an optional breakpoint), never a glyph-eating
    # \discretionary/\char/\slash substitution (checked against CODE, not the
    # comment prose which legitimately names these rejected alternatives).
    assert "\\discretionary" not in code and "\\slash" not in code, (
        "must not use \\discretionary/\\slash (they dropped the char in live testing)"
    )


def test_prose_texttt_scopes_emergencystretch_inside_texttt(tmp_path):
    """\\emergencystretch (the tolerance that lets the breakpoints be taken) must
    live INSIDE the \\texttt redefinition, NOT in a \\begingroup that reverts it
    before \\par (that reverted too early and worsened overflow to 70pt), and NOT
    document-global (would loosen texttt-free prose)."""
    preamble = _preamble(tmp_path)
    m = re.search(r"^\s*\\renewcommand\{\\texttt\}\[1\]\{.*$", preamble, re.MULTILINE)
    assert m, "no \\renewcommand{\\texttt}[1]{...} in preamble"
    line = m.group(0)
    assert "\\setlength{\\emergencystretch}{3em}" in line, (
        "\\texttt redefinition must raise \\emergencystretch so the breakpoints are taken"
    )
    assert "\\PLorigtexttt{\\PLttbreak{#1}}" in line, (
        "\\texttt must break its argument via \\PLttbreak then typeset with the saved "
        "original \\texttt (\\PLorigtexttt) to keep the monospace font"
    )
    assert "\\begingroup" not in line, (
        "\\emergencystretch must NOT be wrapped in \\begingroup — that reverts it "
        "before the enclosing \\par reads it and worsened overflow to 70pt in testing"
    )


def test_prose_texttt_saves_original_before_renewcommand(tmp_path):
    """\\PLorigtexttt must capture the real \\texttt via \\let BEFORE the
    \\renewcommand, otherwise the redefinition recurses into itself (infinite loop
    / TeX capacity exceeded)."""
    preamble = _preamble(tmp_path)
    save_at = preamble.index("\\let\\PLorigtexttt\\texttt")
    renew_at = preamble.index("\\renewcommand{\\texttt}")
    assert save_at < renew_at, (
        "\\let\\PLorigtexttt\\texttt must precede \\renewcommand{\\texttt} to avoid recursion"
    )


def test_table_texttt_breaks_after_every_token(tmp_path):
    """Live residual (v3_e9f0eae7e200 claim-evidence longtable, 8.6pt): tables
    are already scriptsize and \\PLttbreak gives break points after _ / . = —
    but a narrow p-column cannot fit even one unbroken fragment
    ("experiments"), so the cell still overflows by a few pt. Inside table
    environments a tt path token may break ANYWHERE: \\PLttbreakall re-emits
    every token followed by \\penalty0 (same tl_map mechanism as \\PLttbreak —
    glyph-preserving, pandoc \\_ escapes stay intact), and longtable/tabular
    scope \\texttt to it. Prose \\texttt is untouched."""
    preamble = _preamble(tmp_path)

    assert "\\NewDocumentCommand{\\PLttbreakall}{m}{\\pl_ttbreakall:n{#1}}" in preamble
    assert "\\tl_map_inline:nn" in preamble  # same safe token-list walk
    # table environments rebind \texttt to the break-anywhere variant
    assert preamble.count("\\PLorigtexttt{\\PLttbreakall{#1}}") >= 2, (
        "longtable AND tabular must scope \\texttt to the break-anywhere variant"
    )
    # prose \texttt keeps the separator-only breaker
    assert "\\PLorigtexttt{\\PLttbreak{#1}}" in preamble
