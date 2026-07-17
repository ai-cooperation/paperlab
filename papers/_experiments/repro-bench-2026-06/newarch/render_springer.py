"""Deterministic real-Springer (elsarticle) render via Quarto + xelatex.

Produces a journal-formatted paper_draft_v0.pdf from paper_draft_v0.qmd using the
quarto-journals/elsevier extension (elsarticle.cls) + scientometrics.csl — the same
stack the Paper Lab Scientometrics papers use.

Core philosophy (matches the rest of the pipeline): the weak generation model cannot
be trusted to emit perfect journal frontmatter, so we NORMALISE it deterministically
(Paper-1 / Scientometrics standard) before handing off to Quarto. Bib HTML-entity
corruption (`&amp;`) is likewise sanitised deterministically — xelatex treats a bare
`&` as an alignment tab and aborts otherwise.

Falls back to the reportlab renderer at the call site if Quarto is unavailable.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS = SCRIPT_DIR / "assets"
QUARTO_BIN = os.environ.get("PAPER_QUARTO_BIN", str(Path.home() / "opt" / "quarto" / "bin" / "quarto"))

DEFAULT_KEYWORDS = ["reproducible benchmark", "text classification", "machine learning"]


def quarto_available() -> bool:
    return Path(QUARTO_BIN).is_file() or shutil.which("quarto") is not None


def _quarto() -> str:
    return QUARTO_BIN if Path(QUARTO_BIN).is_file() else "quarto"


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_text_without_fences, body)."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def _old_title(fm: str, contract: dict[str, Any]) -> str:
    m = re.search(r'(?m)^title:\s*"?(.+?)"?\s*$', fm)
    if m and m.group(1).strip():
        return m.group(1).strip().strip('"')
    return str(contract.get("topic") or "Research Manuscript").strip()


def _extract_abstract(fm: str, body: str) -> tuple[str, str, str]:
    """Pull the abstract out of a leading Abstract section (any heading level —
    the revision loop rewrites `# Abstract` as `## Abstract`) or the old
    frontmatter. Also captures a trailing `**Keywords:** ...` line the writer
    put inside the section. Returns (abstract, body_without_section, keywords_line)."""
    # The abstract marker varies with how the writer emitted it (all seen in
    # production, all the same double-Abstract breakout when missed):
    #   '# Abstract', '## Abstract', '# Abstract {.unnumbered}' (Pandoc attr),
    #   or a bold '**Abstract**' line (0deb). Match any of them; the section
    #   ends at the next heading OR the next bold marker line. Missing it
    #   injected an 'Abstract pending.' stub AND left the real body Abstract
    #   in place, rendering two Abstracts.
    am = re.search(
        r"(?ms)^(?:#{1,3}\s*Abstract\s*(?:\{[^}\n]*\})?|\*\*\s*Abstract\s*\*\*)\s*\n+"
        r"(.*?)(?=\n#{1,3}\s|\n\*\*\s*(?!Keywords)[A-Z])",
        body,
    )
    if am:
        text = am.group(1)
        body = body[: am.start()] + body[am.end():]
        kw_line = ""
        km = re.search(r"(?mi)^\*{0,2}\s*Keywords?\s*\*{0,2}\s*[:：]\s*(.+?)\s*$", text)
        if km:
            kw_line = km.group(1).strip().strip("*").strip()
            text = text[: km.start()] + text[km.end():]
        return _sanitize_abstract(" ".join(text.split())), body, kw_line
    fm_abs = re.search(r"(?ms)^abstract:\s*\|?\s*\n((?:[ \t]+.*\n?)+)", fm)
    if fm_abs:
        return _sanitize_abstract(" ".join(fm_abs.group(1).split())), body, ""
    fm_abs1 = re.search(r'(?m)^abstract:\s*"?(.+?)"?\s*$', fm)
    if fm_abs1:
        return _sanitize_abstract(fm_abs1.group(1).strip()), body, ""
    return "", body, ""


def _sanitize_abstract(text: str) -> str:
    """Remove flattened YAML frontmatter that a model can accidentally append to
    the abstract. This keeps Quarto metadata keys out of the abstract paragraph
    without trying to interpret the whole frontmatter as YAML."""
    text = " ".join(text.split())
    leak = re.search(
        r"\b(?:keywords|format|bibliography|csl|number-sections|link-citations|toc|geometry)\s*:",
        text,
        re.IGNORECASE,
    )
    if leak:
        text = text[: leak.start()].rstrip(" ,-;")
    return text


def _frontmatter_block(fm: str, key: str) -> str:
    match = re.search(
        r"(?ms)^" + re.escape(key) + r":\s*\n(.*?)(?=^[A-Za-z0-9_-]+:\s*|\Z)",
        fm,
    )
    return match.group(1) if match else ""


def _valid_keyword(keyword: str) -> bool:
    lowered = keyword.strip().lower()
    if not (2 < len(keyword) < 40):
        return False
    if ":" in keyword or "=" in keyword:
        return False
    if lowered in {
        "format",
        "bibliography",
        "csl",
        "number-sections",
        "link-citations",
        "toc",
        "geometry",
    }:
        return False
    return True


def _extract_keywords(fm: str, contract: dict[str, Any], body_kw: str = "") -> list[str]:
    found: list[str] = []
    if body_kw:
        found = [k.strip() for k in re.split(r"[;,、；]", body_kw) if k.strip()]
    if not found:
        block = _frontmatter_block(fm, "keywords")
        if block:
            found = [re.sub(r"^\s*-\s*", "", ln).strip()
                     for ln in block.splitlines() if re.match(r"^\s*-\s+", ln)]
    found = [k for k in found if _valid_keyword(k)][:8]
    # Augment when the writer supplied too few (e.g. a single junk keyword
    # "strategy"). The data_source.name carries the English topic terms even when
    # the title is Chinese (so the latin-token seed below isn't empty).
    if len(found) < 3:
        seed = " ".join(str(contract.get(k) or "") for k in ("topic", "method", "contribution"))
        seed += " " + str((contract.get("data_source") or {}).get("name") or "")
        stop = {"with", "from", "this", "that", "their", "using", "based", "analysis",
                "extension", "adults", "adult", "study", "studies"}
        have = {k.lower() for k in found}
        for t in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", seed):
            tl = t.lower()
            if tl not in stop and tl not in have:
                found.append(tl)
                have.add(tl)
            if len(found) >= 5:
                break
    return found[:6] or DEFAULT_KEYWORDS


def _normalize_tables(body: str) -> str:
    """Give wide markdown tables explicit column widths so a long first-column row
    label (e.g. "LogisticRegression") no longer overprints the next column. Pandoc
    leaves an unwidthed pipe table as non-wrapping columns that overflow; an explicit
    tbl-colwidths forces wrapping p{} columns with the label column weighted wider."""
    lines = body.split("\n")
    sep_re = re.compile(r"^\|?[\s:|-]*-[\s:|-]*\|[\s:|-]*$")
    for i, ln in enumerate(lines):
        m = re.search(r"\{#tbl-[^}]*\}", ln)
        if not m or "tbl-colwidths" in ln:
            continue
        ncol = None
        sep_idx = None
        for j in range(i - 1, max(-1, i - 60), -1):
            s = lines[j].strip()
            if "|" in s and sep_re.match(s) and "-" in s:
                ncol = len([c for c in s.strip("|").split("|") if c.strip() != "" or True])
                sep_idx = j
                break
        if not ncol or ncol < 5:
            continue  # only wide tables overflow the single column
        widths = _table_colwidths(lines, sep_idx or i, i, ncol)
        widths[-1] += 100 - sum(widths)
        attr = m.group(0)[:-1] + f' tbl-colwidths="{widths}"}}'
        lines[i] = ln[: m.start()] + attr + ln[m.end():]
    return "\n".join(lines)


def _table_colwidths(lines: list[str], sep_idx: int, caption_idx: int, ncol: int) -> list[int]:
    rows: list[list[str]] = []
    for idx in range(max(0, sep_idx - 1), caption_idx):
        line = lines[idx].strip()
        if "|" not in line or re.match(r"^\|?[\s:|-]*-[\s:|-]*\|[\s:|-]*$", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == ncol:
            rows.append(cells)
    if not rows:
        weights = [2.4] + [1.0] * (ncol - 1)
    else:
        weights = []
        for col in range(ncol):
            max_len = max(len(row[col]) for row in rows)
            numeric = sum(1 for row in rows[1:] if re.fullmatch(r"[-+−]?\d+(?:\.\d+)?%?", row[col] or ""))
            numeric_ratio = numeric / max(1, len(rows) - 1)
            if numeric_ratio >= 0.6:
                weights.append(max(0.8, min(1.2, max_len / 10)))
            else:
                weights.append(max(1.0, min(3.4, max_len / 18)))
    total = sum(weights)
    widths = [max(6, round(weight / total * 100)) for weight in weights]
    while sum(widths) > 100:
        idx = max(range(len(widths)), key=widths.__getitem__)
        widths[idx] -= 1
    while sum(widths) < 100:
        idx = max(range(len(widths)), key=lambda k: weights[k])
        widths[idx] += 1
    # Content-weight shares can starve a column below its longest UNBREAKABLE
    # word ("documents" = 9 chars needed ~10.4% but got 7% -> Overfull 8.6pt,
    # Gate Z block, v3_e9f0eae7e200). A p-column cannot fit less than one word
    # and TeX will not hyphenate a cell's first word, so enforce a per-column
    # floor of ~1.15% per character of the longest plain token (code spans are
    # excluded: tt breaks anywhere inside tables via the PLttbreakall
    # preamble). Deficits are reclaimed from columns with the most slack above
    # their own floor; floors are capped so one huge token cannot eat the row.
    floors = [
        min(28, max(6, -(-int(_longest_plain_token(rows, col) * 115) // 100)))
        for col in range(ncol)
    ]
    for col in range(ncol):
        while widths[col] < floors[col]:
            donors = [k for k in range(ncol) if k != col and widths[k] > floors[k]]
            if not donors:
                break  # physics limit: floors exceed 100, deliver best effort
            donor = max(donors, key=lambda k: widths[k] - floors[k])
            widths[donor] -= 1
            widths[col] += 1
    return widths


def _longest_plain_token(rows: list[list[str]], col: int) -> int:
    longest = 0
    for row in rows:
        cell = re.sub(r"`[^`]*`", " ", row[col] or "")  # code spans break anywhere
        for token in cell.split():
            longest = max(longest, len(token))
    return longest


_FIG_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)\{#fig-[^}]*\}")


def _normalize_figures(body: str) -> str:
    """A figure cross-reference (@fig-x) only resolves if its image is a STANDALONE
    paragraph — Quarto then makes it a labeled float. Writers sometimes leave the
    image inline with prose ("... shown in @fig-x. ![cap](p){#fig-x}"), which
    renders as an unlabeled inline image and yields an unresolved ?@fig-x. Force
    every ![...]{#fig-...} onto its own paragraph (blank line before and after)."""
    out: list[str] = []
    for line in body.split("\n"):
        m = _FIG_IMG.search(line)
        if not m or line.strip() == m.group(0):
            out.append(line)
            continue
        before, after = line[: m.start()].rstrip(), line[m.end():].lstrip()
        if before:
            out.extend([before, ""])
        out.append(m.group(0))
        out.append("")
        if after:
            out.append(after)
    return "\n".join(out)


def _isolate_generated(body: str) -> str:
    """A GENERATED table block must be its own paragraph or pandoc won't parse the
    caption's {#tbl-id} attribute (it appears raw, and @tbl-id can't resolve). The
    writer sometimes embeds the placeholder mid-sentence ("...summarised in
    <!-- GENERATED:tbl-studies -->| ... |"), gluing prose to the block. Force a
    blank line before every open marker and after every close marker."""
    body = re.sub(r"(\S)[ \t]*(<!-- GENERATED:)", r"\1\n\n\2", body)
    body = re.sub(r"(<!-- /GENERATED:[^>]*-->)[ \t]*(\S)", r"\1\n\n\2", body)
    return body


def _strip_crossref_prefixes(body: str) -> str:
    """Quarto auto-prepends "Table"/"Figure" to a @tbl-/@fig- cross-reference, so a
    writer who pens "Table @tbl-main" / "Figure @fig-forest" gets "Table Table 1" /
    "Figure Figure 2". Strip the redundant leading word before the reference."""
    return re.sub(r"\b(?:Table|Figure|Fig\.?|Tab\.?)\s+(@(?:tbl|fig)-)", r"\1", body)


def _strip_trailing_references(body: str) -> str:
    # Quarto regenerates the bibliography; a hand-written `# References` heading at the
    # very end would otherwise double up.
    return re.sub(r"(?ms)\n#\s*References\s*\n*\Z", "\n", body)


def _strip_assembled_abstract_block(body: str, abstract_rel: str) -> str:
    """ADR-001 path: the assembler wrapped the abstract in its OWN source-map
    markers, so the springer derivation cuts that exact block — no heading-variant
    regex (the class that produced the double-Abstract treadmill)."""
    if not abstract_rel:
        return body
    pattern = r"(?s)<!--\s*SOURCE:\s*%s\s*-->.*?<!--\s*END SOURCE:\s*%s\s*-->\n?" % (
        re.escape(abstract_rel),
        re.escape(abstract_rel),
    )
    return re.sub(pattern, "", body)


def normalize_frontmatter(run_dir: Path, contract: dict[str, Any], src_name: str = "paper_draft_v0.qmd",
                          out_name: str = "paper_springer.qmd",
                          ir_values: dict[str, Any] | None = None) -> Path:
    """Write a journal-normalised COPY (out_name) of the canonical qmd. The canonical
    paper_draft_v0.qmd is left untouched so the consistency / claim-evidence / prose
    gates keep operating on the model's original output.

    ir_values (ADR-001 new-architecture runs): title/abstract/keywords come from the
    validated IR (paper_meta.json + sections/00_abstract.md) — never re-extracted
    from the qmd by regex — and the body abstract block is removed via the
    assembler's exact source-map markers. Legacy runs (ir_values=None) keep the
    extraction path unchanged until live validation retires it."""
    qmd = run_dir / src_name
    text = qmd.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    if ir_values is not None:
        title = str(ir_values.get("title") or "").strip() or _old_title(fm, contract)
        abstract = str(ir_values.get("abstract") or "").strip()
        if not abstract:
            # Fail loudly: the assembler fail-closes on a missing abstract, so an
            # empty value here is a broken contract, never a stub-injection point.
            raise ValueError("ir_values.abstract is empty; assembler contract violated")
        body = _strip_assembled_abstract_block(body, str(ir_values.get("abstract_ref") or ""))
        keywords = [str(k) for k in (ir_values.get("keywords") or []) if _valid_keyword(str(k))]
        if len(keywords) < 3:
            keywords = _extract_keywords(fm, contract, "")
    else:
        title = _old_title(fm, contract)
        abstract, body, body_kw = _extract_abstract(fm, body)
        keywords = _extract_keywords(fm, contract, body_kw)
    body = _strip_trailing_references(body)
    body = _isolate_generated(body)
    body = _strip_crossref_prefixes(body)
    body = _normalize_tables(body)
    body = _normalize_figures(body).lstrip("\n")

    abstract = abstract or "Abstract pending."
    abs_yaml = "\n".join("  " + line for line in re.findall(r".{1,110}(?:\s|$)", abstract))
    kw_yaml = "\n".join(f"  - {k}" for k in keywords)
    journal = str(contract.get("target_journal") or "Scientometrics").strip() or "Scientometrics"

    # Chinese-output papers: without a CJK font xelatex silently DROPS every CJK
    # glyph (a 6,244-char zh paper rendered to a PDF with 0 CJK chars). Detect
    # CJK in the content and wire Noto Serif CJK TC via pandoc's CJKmainfont.
    has_cjk = bool(re.search(r"[一-鿿]", body + title + abstract))
    cjk_yaml = 'CJKmainfont: "Noto Serif CJK TC"\n' if has_cjk else ""

    title_esc = title.replace('"', r"\"")
    new_fm = (
        "---\n"
        f'title: "{title_esc}"\n'
        "author:\n"
        "  - name: Cooperation.TW\n"
        "    email: paperlab@cooperation.tw\n"
        "    affiliations:\n"
        "      - id: pl\n"
        "        name: Paper Lab\n"
        "        city: Taipei\n"
        "        country: Taiwan\n"
        "    attributes:\n"
        "      corresponding: true\n"
        "date: last-modified\n"
        "abstract: |\n"
        f"{abs_yaml}\n"
        "keywords:\n"
        f"{kw_yaml}\n"
        "format:\n"
        "  elsevier-pdf:\n"
        "    keep-tex: true\n"
        "    pdf-engine: xelatex\n"
        "    journal:\n"
        f"      name: {journal}\n"
        "      formatting: review\n"
        "      model: 3p\n"
        "      cite-style: authoryear\n"
        "    include-in-header:\n"
        "      text: |\n"
        "        \\usepackage{etoolbox}\n"
        "        % Long DOIs/URLs break lines (guards future URL-class Overfull). Load\n"
        "        % defensively: pandoc already \\IfFileExists-guards xurl, so mirror that\n"
        "        % and never hard-fail a render on a xurl-less TeX install. Idempotent.\n"
        "        \\IfFileExists{xurl.sty}{\\usepackage{xurl}}{}\n"
        "        \\usepackage{setspace}\n"
        "        % Wide numeric tables must shrink to fit the single column without\n"
        "        % long row labels colliding into the next column. Tables are single-\n"
        "        % spaced like the reference list (review formatting double-spaces body).\n"
        "        %\n"
        "        % OVERFULL \\hbox PREVENTION (deterministic; do NOT add a model repair\n"
        "        % round for this). A 7-column longtable squeezed into elsarticle's single\n"
        "        % column leaves the narrowest p{} cells only ~0.4in wide. Long slash-\n"
        "        % joined tokens (abstract/metadata, Subject/outcome, Crossref/OpenAlex,\n"
        "        % Difference-in-differences/event) have no legal break point inside the\n"
        "        % cell, so LaTeX cannot hyphenate them: each is one unbreakable box that\n"
        "        % overflows by ~17pt. \\sloppy/\\emergencystretch/\\hyphenpenalty are\n"
        "        % all useless here -- there is no interword glue and no in-word break to\n"
        "        % exploit. The only fix that reaches Gate Z=0 is to MAKE the slash a\n"
        "        % break opportunity. \\PLbreakslashes makes '/' an active char whose\n"
        "        % meaning is a REAL catcode-12 slash (\\string/, so the glyph is never\n"
        "        % dropped -- \\char/\\slash/\\discretionary all silently ate the slash in\n"
        "        % testing) followed by a neutral \\penalty0 break. Live-verified on job\n"
        "        % v3_72f87c735de5: Gate Z Overfull 11 -> 0 (log total 17 -> 0), all\n"
        "        % slashes preserved in the rendered PDF, body prose and reference-list\n"
        "        % URLs unaffected (the active catcode is scoped to table envs and auto-\n"
        "        % reverts on \\end). The lowercase trick is the standard idiom for\n"
        "        % defining an active character's meaning in the preamble -- a plain\n"
        "        % \\def/ would bind the catcode-12 slash, not the active one, and the\n"
        "        % PDF would drop the slash. Font is also stepped to \\scriptsize and\n"
        "        % \\sloppy + \\emergencystretch kept as belt-and-braces for any residual\n"
        "        % non-slash overflow.\n"
        "        \\begingroup\\lccode`\\~=`\\/\\relax\n"
        "        \\lowercase{\\endgroup\\def\\PLslashdef{\\def~{\\string/\\penalty0 }}}\n"
        "        \\newcommand{\\PLbreakslashes}{\\catcode`\\/=13\\relax\\PLslashdef}\n"
        "        \\AtBeginEnvironment{longtable}{\\singlespacing\\scriptsize\\sloppy\\setlength{\\emergencystretch}{3em}\\PLbreakslashes}\n"
        "        \\AtBeginEnvironment{tabular}{\\singlespacing\\footnotesize\\sloppy\\setlength{\\emergencystretch}{3em}\\PLbreakslashes}\n"
        "        % PROSE \\texttt OVERFULL PREVENTION (job v3_4dc73d199e17, accounting).\n"
        "        % Distinct class from the table slash-break above: long \\texttt{} inline\n"
        "        % code in BODY PROSE (real_experiments/real_results.json,\n"
        "        % analysis_type = deterministic_reference_evidence_map) are unbreakable boxes\n"
        "        % that overflow by up to 49.5pt -- the table-scoped \\PLbreakslashes never\n"
        "        % fires here. Fix = redefine \\texttt to walk its argument as a TOKEN LIST\n"
        "        % (\\tl_map_inline, NOT \\str_map which would stringify the pandoc \\_ / \\\\ \n"
        "        % escapes into literal backslashes and CORRUPT the glyph) and append a\n"
        "        % neutral \\penalty0 AFTER each break-worthy token (\\_ / . =). The original\n"
        "        % token is re-emitted UNTOUCHED first, so every glyph is preserved by\n"
        "        % construction -- unlike \\char/\\slash/\\discretionary/active-catcode\n"
        "        % rewrites, which dropped or mangled chars in live testing. Breakpoints\n"
        "        % alone are inert without tolerance, so \\emergencystretch is raised INSIDE\n"
        "        % the redefined \\texttt: it is read at the enclosing \\par, so it scopes to\n"
        "        % ONLY paragraphs that contain a \\texttt (texttt-free prose keeps tight\n"
        "        % justification; verified lipsum-clean). Live-verified job v3_4dc73d199e17:\n"
        "        % Gate Z Overfull(>=5pt) 2 -> 0, all glyphs intact in the rendered PDF.\n"
        "        \\ExplSyntaxOn\n"
        "        \\cs_new_protected:Npn \\pl_ttbreak:n #1 {\n"
        "          \\tl_map_inline:nn {#1} {\n"
        "            ##1\n"
        "            \\tl_if_eq:nnT {##1} {\\_} {\\penalty0}\n"
        "            \\str_if_eq:nnT {##1} {/} {\\penalty0}\n"
        "            \\str_if_eq:nnT {##1} {.} {\\penalty0}\n"
        "            \\str_if_eq:nnT {##1} {=} {\\penalty0}\n"
        "          }\n"
        "        }\n"
        "        \\NewDocumentCommand{\\PLttbreak}{m}{\\pl_ttbreak:n{#1}}\n"
        "        % Tables are a THIRD class: cells are already scriptsize p-columns, but a\n"
        "        % narrow column cannot fit even one unbroken fragment between separators\n"
        "        % (live: v3_e9f0eae7e200 claim-evidence longtable, 'experiments' fragment,\n"
        "        % 8.6pt over). Inside table environments a tt path token may break ANYWHERE:\n"
        "        % same glyph-preserving tl_map walk, but \\penalty0 after EVERY token.\n"
        "        \\cs_new_protected:Npn \\pl_ttbreakall:n #1 {\n"
        "          \\tl_map_inline:nn {#1} {\n"
        "            ##1\n"
        "            \\penalty0\n"
        "          }\n"
        "        }\n"
        "        \\NewDocumentCommand{\\PLttbreakall}{m}{\\pl_ttbreakall:n{#1}}\n"
        "        \\ExplSyntaxOff\n"
        "        \\let\\PLorigtexttt\\texttt\n"
        "        \\renewcommand{\\texttt}[1]{\\setlength{\\emergencystretch}{3em}\\PLorigtexttt{\\PLttbreak{#1}}}\n"
        "        \\AtBeginEnvironment{longtable}{\\renewcommand{\\texttt}[1]{\\PLorigtexttt{\\PLttbreakall{#1}}}}\n"
        "        \\AtBeginEnvironment{tabular}{\\renewcommand{\\texttt}[1]{\\PLorigtexttt{\\PLttbreakall{#1}}}}\n"
        "        % Journal convention: double-spaced body (review), single-spaced\n"
        "        % bibliography. Quarto/CSL emits the reference list as CSLReferences.\n"
        "        \\AtBeginEnvironment{CSLReferences}{\\singlespacing}\n"
        "        \\AtBeginEnvironment{thebibliography}{\\singlespacing}\n"
        "csl: scientometrics.csl\n"
        "bibliography: references.bib\n"
        f"{cjk_yaml}"
        "number-sections: true\n"
        "link-citations: true\n"
        "---\n\n"
    )
    out = run_dir / out_name
    out.write_text(new_fm + body, encoding="utf-8")
    return out


_HTML_ENTITIES = (("&amp;", r"\&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'))


def sanitize_bib(run_dir: Path) -> None:
    bib = run_dir / "references.bib"
    if not bib.is_file():
        return
    t = bib.read_text(encoding="utf-8")
    for ent, rep in _HTML_ENTITIES:
        t = t.replace(ent, rep)
    # Escape any remaining bare ampersand (xelatex alignment-tab trap) without
    # double-escaping an already-escaped \&.
    t = re.sub(r"(?<!\\)&", r"\\&", t)
    # Collapse double-escapes to exactly one backslash: `\&amp;` becomes `\\&` via
    # the entity pass above, and historic runs carry `\\&` outright — both compile
    # as linebreak + BARE alignment tab and crash xelatex (live proof 2026-07-09,
    # golden bib line 109; the exact trap the ADR-001 v2 review predicted). A
    # backslash run before & is never legitimate in a bib field. Idempotent.
    t = re.sub(r"\\{2,}&", r"\\&", t)
    bib.write_text(t, encoding="utf-8")


def ensure_assets(run_dir: Path) -> None:
    ext_src = ASSETS / "_extensions"
    if ext_src.is_dir():
        shutil.copytree(ext_src, run_dir / "_extensions", dirs_exist_ok=True)
    csl_src = ASSETS / "scientometrics.csl"
    if csl_src.is_file():
        shutil.copy2(csl_src, run_dir / "scientometrics.csl")


def _ir_values(run_dir: Path) -> dict[str, Any] | None:
    """Structural render values from the ADR-001 IR when this is a new-architecture
    run (paper_meta.json present + valid). None -> legacy extraction path. Lazy
    import + broad guard: a broken meta must degrade to the legacy path, never crash
    a render (the assembly gates surface the block report separately)."""
    try:
        from engine_v3.assembly import ir_render_values

        return ir_render_values(run_dir)
    except Exception:  # noqa: BLE001 - render must not die on assembly import/meta issues
        return None


def render(run_dir: Path, contract: dict[str, Any] | None = None, timeout_s: int = 420) -> bool:
    """Normalise + render paper_draft_v0.qmd to a real elsarticle PDF. Returns True on
    a valid PDF, False otherwise (caller may fall back to reportlab)."""
    run_dir = Path(run_dir)
    qmd = run_dir / "paper_draft_v0.qmd"
    pdf = run_dir / "paper_draft_v0.pdf"
    if not qmd.is_file() or not quarto_available():
        return False
    if contract is None:
        contract = {}
        cpath = run_dir / "research_contract.json"
        if cpath.is_file():
            try:
                contract = json.loads(cpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                contract = {}
    log_dir = run_dir / "_phase_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    work_name = "paper_springer.qmd"
    work_pdf = run_dir / "paper_springer.pdf"
    try:
        normalize_frontmatter(run_dir, contract, out_name=work_name, ir_values=_ir_values(run_dir))
        sanitize_bib(run_dir)
        ensure_assets(run_dir)
    except Exception as exc:  # normalisation must never hard-crash the pipeline
        (log_dir / "render_springer.stderr.txt").write_text(f"normalize failed: {exc}", encoding="utf-8")
        return False
    env = os.environ.copy()
    env.setdefault("QUARTO_NO_TINYTEX", "1")
    proc = subprocess.run(
        [_quarto(), "render", work_name, "--to", "elsevier-pdf"],
        cwd=run_dir, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout_s, env=env,
    )
    if work_pdf.is_file() and work_pdf.stat().st_size > 1000:
        _finish_citations(run_dir, work_pdf, log_dir)
        shutil.move(str(work_pdf), str(pdf))
        return True
    (log_dir / "render_springer.stderr.txt").write_text(
        (proc.stderr or proc.stdout or "")[-3000:], encoding="utf-8")
    return False


def _pdf_has_unresolved_citations(pdf: Path) -> bool:
    try:
        out = subprocess.run(["pdftotext", str(pdf), "-"], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60).stdout
    except Exception:  # noqa: BLE001 - cannot inspect -> assume fine, gate re-checks
        return False
    return out.count("(?)") >= 3


def _finish_citations(run_dir: Path, work_pdf: Path, log_dir: Path) -> None:
    """Deterministic natbib + crossref finisher. Quarto's single pass leaves a
    bibtex/natbib doc with `(?)` citations, an empty References list, AND
    unresolved \\ref crossrefs (?@tbl-/?@fig-). Run the classic
    xelatex -> bibtex -> xelatex -> xelatex cycle ourselves: bibtex builds the
    bibliography and the extra xelatex passes resolve every \\ref.

    TRIGGER on the doc being bibtex-based (has \\bibliography{}) — NOT a fragile
    `(?)` string match: natbib/elsevier render unresolved citations in a form
    pdftotext does not surface as `(?)`, so the old gate false-negatived and the
    finisher silently never ran (delivered PDFs shipped with ?@tbl-/?@fig- and no
    References). Same philosophy as the table/figure gates: never trust the
    toolchain's claim, mechanically finish."""
    tex = run_dir / "paper_springer.tex"
    if not tex.is_file():
        return
    try:
        tex_src = tex.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return
    bibtex_based = "\\bibliography{" in tex_src
    if not (bibtex_based or _pdf_has_unresolved_citations(work_pdf)):
        return

    def _run(cmd: list[str], timeout: int) -> None:
        subprocess.run(cmd, cwd=run_dir, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=timeout)
    try:
        _run(["xelatex", "-interaction=nonstopmode", tex.name], 300)
        if bibtex_based:
            _run(["bibtex", "paper_springer"], 120)
        _run(["xelatex", "-interaction=nonstopmode", tex.name], 300)
        _run(["xelatex", "-interaction=nonstopmode", tex.name], 300)
        # verify both citations and crossrefs resolved in the rebuilt PDF
        leftover = _pdf_unresolved_count(work_pdf)
        (log_dir / "render_finisher.txt").write_text(
            f"finisher ran (bibtex={bibtex_based}); unresolved markers after: {leftover}",
            encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - finisher is best-effort; gate catches leftovers
        (log_dir / "render_finisher.txt").write_text(f"finisher failed: {exc}", encoding="utf-8")


def _pdf_unresolved_count(pdf: Path) -> int:
    """Count residual unresolved markers (citations `(?)` and crossrefs `?@`/`??`)."""
    try:
        out = subprocess.run(["pdftotext", str(pdf), "-"], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60).stdout
    except Exception:  # noqa: BLE001
        return 0
    return out.count("(?)") + len(re.findall(r"\?@|\?\?", out))


if __name__ == "__main__":
    import sys
    rd = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    print(json.dumps({"ok": render(rd)}, ensure_ascii=False))
