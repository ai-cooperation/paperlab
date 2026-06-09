#!/usr/bin/env python3
"""Springer-style (Scientometrics) ReportLab renderer for paper-draft QMD output.

Deterministic render step when Quarto/LaTeX are unavailable (ac-2012 has only
reportlab). Parses YAML frontmatter (incl. the abstract block), resolves
@-citations to blue hyperlinked author-year, numbers sections, lays out booktabs
tables, captions figures, and appends a hanging bibliography.

Unicode: registers DejaVu Serif (normal/bold — full glyph coverage incl. — – ∈ α)
plus Liberation Serif italics, so academic symbols render instead of tofu boxes.
Falls back to the built-in Times/Helvetica if those TTFs are absent (no crash).

Usage: render_qmd_reportlab.py <qmd> <pdf> [--bib references.bib]
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

NO_NUMBER_HEADINGS = {"abstract", "references", "keywords", "acknowledgements", "acknowledgments"}
CITE_COLOR = "#0b5394"  # blue, hyperlinked
DEJAVU = "/usr/share/fonts/truetype/dejavu"
LIBERATION = "/usr/share/fonts/truetype/liberation"

# Replacements for the rare glyphs even Liberation italics may miss, so an italic
# span never tofus. (Normal/bold DejaVu covers these; this only guards italics.)
GLYPH_FALLBACK = {"∈": " in ", "∉": " not in "}

# Inline LaTeX math ($...$) -> Unicode (DejaVu renders these). QMD tables/text use
# $\pm$, $\alpha$, etc.; without this they print the raw "$\pm$".
LATEX_MATH = {
    r"\pm": "±", r"\mp": "∓", r"\times": "×", r"\cdot": "·", r"\div": "÷",
    r"\leq": "≤", r"\le": "≤", r"\geq": "≥", r"\ge": "≥", r"\neq": "≠",
    r"\approx": "≈", r"\sim": "~", r"\propto": "∝", r"\infty": "∞", r"\to": "→", r"\rightarrow": "→",
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ", r"\epsilon": "ε", r"\mu": "µ",
    r"\sigma": "σ", r"\rho": "ρ", r"\lambda": "λ", r"\tau": "τ", r"\theta": "θ", r"\chi": "χ",
    r"\kappa": "κ", r"\eta": "η", r"\phi": "φ", r"\pi": "π", r"\Delta": "Δ", r"\%": "%", r"\,": " ",
}


def latex_math_to_unicode(text: str) -> str:
    def repl(m: re.Match) -> str:
        s = m.group(1)
        for cmd, sym in sorted(LATEX_MATH.items(), key=lambda kv: -len(kv[0])):
            s = s.replace(cmd, sym)
        s = re.sub(r"\\[a-zA-Z]+", "", s)            # drop unknown commands
        s = s.replace("{", "").replace("}", "").replace("^", "").replace("_", " ")
        return s.strip()
    return re.sub(r"\$([^$]+)\$", repl, text)


def register_fonts() -> dict[str, str]:
    """Register Unicode TTFs; return the font names to use. Falls back to the
    built-in fonts if the TTFs are missing (e.g. when run off-box)."""
    fonts = {"body": "Times-Roman", "head": "Helvetica-Bold", "mono": "Courier"}
    try:
        reg = [
            ("Body", f"{DEJAVU}/DejaVuSerif.ttf"),
            ("Body-Bold", f"{DEJAVU}/DejaVuSerif-Bold.ttf"),
            ("Body-Italic", f"{LIBERATION}/LiberationSerif-Italic.ttf"),
            ("Body-BoldItalic", f"{LIBERATION}/LiberationSerif-BoldItalic.ttf"),
            ("Head", f"{DEJAVU}/DejaVuSans-Bold.ttf"),
            ("Mono", f"{DEJAVU}/DejaVuSansMono.ttf"),
        ]
        if not all(Path(p).is_file() for _, p in reg):
            return fonts
        for name, path in reg:
            pdfmetrics.registerFont(TTFont(name, path))
        pdfmetrics.registerFontFamily(
            "Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic")
        fonts.update(body="Body", head="Head", mono="Mono")
    except Exception:
        pass
    return fonts


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------
def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[3:end], text[nl + 1 :] if nl != -1 else ""
    return "", text


def parse_frontmatter(fm: str) -> dict[str, object]:
    meta: dict[str, object] = {"authors": []}

    def unquote(v: str) -> str:
        return v.strip().strip('"').strip("'").strip()

    cur_author: dict[str, str] | None = None
    in_authors = False
    in_abstract = False
    abstract_lines: list[str] = []
    for line in fm.splitlines():
        # abstract: |  (YAML literal block — collect indented continuation lines)
        if in_abstract:
            if line.strip() == "" or line.startswith((" ", "\t")):
                abstract_lines.append(line.strip())
                continue
            in_abstract = False  # dedent ends the block
        m_title = re.match(r"^title:\s*(.+)$", line)
        m_date = re.match(r"^date:\s*(.+)$", line)
        m_bib = re.match(r"^bibliography:\s*(.+)$", line)
        m_kw = re.match(r"^keywords:\s*(.+)$", line)
        m_abs = re.match(r"^abstract:\s*(\|?>?\s*)(.*)$", line)
        if m_title:
            meta["title"] = unquote(m_title.group(1)); in_authors = False
        elif m_abs:
            in_authors = False
            inline_val = m_abs.group(2).strip()
            if inline_val:
                abstract_lines.append(unquote(inline_val))
            else:
                in_abstract = True
        elif m_date:
            meta["date"] = unquote(m_date.group(1)); in_authors = False
        elif m_bib:
            meta["bibliography"] = unquote(m_bib.group(1)); in_authors = False
        elif m_kw and m_kw.group(1).strip() not in {"", "|"}:
            meta["keywords"] = unquote(m_kw.group(1)); in_authors = False
        elif re.match(r"^author:\s*$", line):
            in_authors = True
        elif in_authors:
            m_name = re.match(r"^\s*-\s*name:\s*(.+)$", line)
            m_aff = re.match(r"^\s*affiliation:\s*(.+)$", line)
            m_email = re.match(r"^\s*email:\s*(.+)$", line)
            if m_name:
                cur_author = {"name": unquote(m_name.group(1))}
                meta["authors"].append(cur_author)  # type: ignore[attr-defined]
            elif m_aff and cur_author is not None:
                cur_author["affiliation"] = unquote(m_aff.group(1))
            elif m_email and cur_author is not None:
                cur_author["email"] = unquote(m_email.group(1))
            elif re.match(r"^\S", line):
                in_authors = False
    if abstract_lines:
        meta["abstract"] = " ".join(x for x in abstract_lines if x).strip()
    return meta


# ---------------------------------------------------------------------------
# BibTeX
# ---------------------------------------------------------------------------
def parse_bib(bib_path: Path) -> dict[str, dict[str, str]]:
    if not bib_path.is_file():
        return {}
    text = bib_path.read_text(encoding="utf-8", errors="ignore")
    entries: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"@\w+\s*\{\s*([^,]+),(.*?)\n\}", text, re.DOTALL):
        key = m.group(1).strip()
        fields: dict[str, str] = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}\s*,?\s*$", m.group(2), re.MULTILINE):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        if key:
            entries[key] = fields
    return entries


def _authors(entry: dict[str, str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for part in re.split(r"\s+and\s+", entry.get("author", "")):
        part = part.strip()
        if not part:
            continue
        if "," in part:
            last, first = part.split(",", 1)
        else:
            toks = part.split()
            last, first = (toks[-1], " ".join(toks[:-1])) if len(toks) > 1 else (part, "")
        out.append((last.strip(), first.strip()))
    return out


def cite_label(entry: dict[str, str]) -> str:
    auths = _authors(entry)
    year = entry.get("year", "n.d.")
    if not auths:
        return year
    if len(auths) == 1:
        name = auths[0][0]
    elif len(auths) == 2:
        name = f"{auths[0][0]} and {auths[1][0]}"
    else:
        name = f"{auths[0][0]} et al."
    return f"{name}, {year}"


def cite_narrative(entry: dict[str, str]) -> str:
    label = cite_label(entry)
    if ", " in label:
        name, year = label.rsplit(", ", 1)
        return f"{name} ({year})"
    return label


def full_reference(entry: dict[str, str]) -> str:
    def initials(first: str) -> str:
        return "".join(p[0].upper() for p in re.split(r"[\s.-]+", first) if p)
    names = ", ".join(f"{last} {initials(first)}".strip() for last, first in _authors(entry)) or "Anon"
    year = entry.get("year", "n.d.")
    title = entry.get("title", "").rstrip(". ")
    journal = entry.get("journal", "").strip()
    doi = entry.get("doi", "").strip()
    ref = f"{names} ({year}) {title}."
    if journal:
        ref += f" {journal}."
    if doi:
        ref += f" https://doi.org/{doi}"
    return re.sub(r"\s+", " ", ref).strip()


# ---------------------------------------------------------------------------
# In-text citations -> blue hyperlinked author-year (applied AFTER inline escaping)
# ---------------------------------------------------------------------------
def replace_citations(text: str, bib: dict[str, dict[str, str]], used: set[str]) -> str:
    def link(key: str, label: str) -> str:
        used.add(key)
        return f'<a href="#cite-{key}" color="{CITE_COLOR}">{label}</a>'

    def render_keys(keys: list[str], narrative: bool) -> str:
        parts: list[str] = []
        for k in keys:
            k = k.lstrip("@").strip()
            if k in bib:
                parts.append(link(k, cite_narrative(bib[k]) if narrative and len(keys) == 1 else cite_label(bib[k])))
            else:
                parts.append(k)
        if narrative and len(keys) == 1:
            return parts[0]
        return "(" + "; ".join(parts) + ")"

    text = re.sub(r"\[[^\]]*@[A-Za-z][^\]]*\]",
                  lambda m: render_keys(re.findall(r"@([A-Za-z0-9_:-]+)", m.group(0)), narrative=False), text)
    text = re.sub(r"(?<![\w\[@])@([A-Za-z][A-Za-z0-9_:-]+)",
                  lambda m: render_keys([m.group(1)], narrative=True), text)
    return text


def inline(text: str) -> str:
    text = latex_math_to_unicode(text)
    for bad, repl in GLYPH_FALLBACK.items():
        text = text.replace(bad, repl)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r"<font face='Mono'>\1</font>", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^)]+)\)", r"\1", text)
    return text


def styles(F: dict[str, str]) -> dict[str, ParagraphStyle]:
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=s["Title"], fontName=F["head"], fontSize=16, leading=20,
                                 alignment=TA_CENTER, spaceAfter=10),
        "authors": ParagraphStyle("authors", parent=s["Normal"], fontName=F["body"], fontSize=11, leading=14,
                                   alignment=TA_CENTER, spaceAfter=2),
        "affil": ParagraphStyle("affil", parent=s["Normal"], fontName=F["body"], fontSize=9, leading=12,
                                 alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=12),
        "abshead": ParagraphStyle("abshead", parent=s["Normal"], fontName=F["head"], fontSize=11, leading=14,
                                   leftIndent=24, spaceBefore=4, spaceAfter=3),
        "abstract": ParagraphStyle("abstract", parent=s["Normal"], fontName=F["body"], fontSize=8.8, leading=11.5,
                                    alignment=TA_JUSTIFY, leftIndent=24, rightIndent=24, spaceAfter=6),
        "keywords": ParagraphStyle("keywords", parent=s["Normal"], fontName=F["body"], fontSize=8.8, leading=11.5,
                                   leftIndent=24, rightIndent=24, spaceAfter=12),
        "h1": ParagraphStyle("h1", parent=s["Heading1"], fontName=F["head"], fontSize=12, leading=15,
                             spaceBefore=10, spaceAfter=5),
        "h2": ParagraphStyle("h2", parent=s["Heading2"], fontName=F["head"], fontSize=10.5, leading=13,
                             spaceBefore=7, spaceAfter=4),
        "body": ParagraphStyle("body", parent=s["BodyText"], fontName=F["body"], fontSize=10, leading=13,
                               alignment=TA_JUSTIFY, spaceAfter=5),
        "caption": ParagraphStyle("caption", parent=s["Normal"], fontName=F["body"], fontSize=8.5, leading=11,
                                  alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
        "tcaption": ParagraphStyle("tcaption", parent=s["Normal"], fontName=F["head"], fontSize=8.8, leading=11,
                                   spaceBefore=8, spaceAfter=3),
        "cell": ParagraphStyle("cell", parent=s["Normal"], fontName=F["body"], fontSize=8.5, leading=10.5),
        "cellh": ParagraphStyle("cellh", parent=s["Normal"], fontName=F["head"], fontSize=8.5, leading=10.5),
        "ref": ParagraphStyle("ref", parent=s["Normal"], fontName=F["body"], fontSize=8.8, leading=11.5,
                              leftIndent=14, firstLineIndent=-14, spaceAfter=3),
    }


def title_block(story: list, meta: dict, st: dict, bib: dict, used: set) -> None:
    story.append(Paragraph(inline(str(meta.get("title") or "Untitled")), st["title"]))
    authors = meta.get("authors") or []
    if authors:
        story.append(Paragraph(inline(", ".join(str(a.get("name", "")) for a in authors)), st["authors"]))
        a0 = authors[0]
        sub = str(a0.get("affiliation", "")) + (f" · {a0.get('email')}" if a0.get("email") else "")
        if sub.strip():
            story.append(Paragraph(inline(sub), st["affil"]))
    if meta.get("date"):
        story.append(Paragraph(inline(str(meta["date"])), st["affil"]))
    if meta.get("abstract"):
        story.append(Paragraph("Abstract", st["abshead"]))
        story.append(Paragraph(replace_citations(inline(str(meta["abstract"])), bib, used), st["abstract"]))
    if meta.get("keywords"):
        story.append(Paragraph("<b>Keywords</b> " + inline(str(meta["keywords"])), st["keywords"]))


def make_table(rows: list[str], st: dict, counter: list[int]) -> list:
    grid = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    grid = [g for g in grid if not re.match(r"^[-:\s|]+$", "|".join(g))]
    if not grid:
        return []
    header, *data = grid
    table_data = [[Paragraph(inline(c), st["cellh"]) for c in header]] + [
        [Paragraph(inline(c), st["cell"]) for c in r] for r in data]
    counter[0] += 1
    tbl = Table(table_data, hAlign="CENTER", repeatRows=1)
    tbl.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.1, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.1, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [Paragraph(f"<b>Table {counter[0]}</b>", st["tcaption"]), tbl, Spacer(1, 8)]


def build_pdf(qmd: Path, pdf: Path, bib_path: Path | None = None) -> None:
    F = register_fonts()
    st = styles(F)
    text = qmd.read_text(encoding="utf-8", errors="ignore")
    fm, body = split_frontmatter(text)
    meta = parse_frontmatter(fm)
    bib = parse_bib(bib_path or (qmd.parent / str(meta.get("bibliography") or "references.bib")))
    used: set[str] = set()

    doc = SimpleDocTemplate(str(pdf), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm, title=str(meta.get("title") or qmd.stem))
    story: list = []
    title_block(story, meta, st, bib, used)

    fig_n, tbl_n, h1_n, h2_n = [0], [0], [0], [0]
    para: list[str] = []
    table_block: list[str] = []
    in_code = False
    section = {"name": ""}

    def flush_para() -> None:
        if para:
            joined = " ".join(p.strip() for p in para if p.strip())
            if joined:
                # escape + inline markup FIRST, then add (unescaped) citation links.
                marked = replace_citations(inline(joined), bib, used)
                style = st["abstract"] if section["name"] == "abstract" else st["body"]
                story.append(Paragraph(marked, style))
            para.clear()

    def flush_table() -> None:
        if table_block:
            story.extend(make_table(table_block, st, tbl_n))
            table_block.clear()

    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            flush_para(); flush_table(); in_code = not in_code; continue
        if in_code:
            continue
        fig = re.match(r"^!\[(.*?)\]\(([^)]+)\)", line)
        if fig:
            flush_para(); flush_table()
            rel = fig.group(2).split("#", 1)[0].strip()
            if rel.lower().endswith(".svg") and (qmd.parent / (rel[:-4] + ".png")).is_file():
                rel = rel[:-4] + ".png"
            img = (qmd.parent / rel).resolve()
            if img.is_file() and rel.lower().endswith((".png", ".jpg", ".jpeg")):
                fig_n[0] += 1
                story.append(Image(str(img), width=5.6 * inch, height=3.5 * inch, kind="proportional"))
                story.append(Paragraph(f"<b>Fig. {fig_n[0]}</b> " + replace_citations(inline(fig.group(1)), bib, used), st["caption"]))
            continue
        if line.startswith("|") and line.rstrip().endswith("|"):
            flush_para(); table_block.append(line); continue
        if table_block:
            flush_table()
        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_para()
            level, htext = len(heading.group(1)), heading.group(2).strip()
            section["name"] = htext.lower().strip()
            if level == 1:
                if section["name"] in NO_NUMBER_HEADINGS:
                    label = htext
                else:
                    h1_n[0] += 1; h2_n[0] = 0; label = f"{h1_n[0]} {htext}"
                story.append(Paragraph(inline(label), st["h1"]))
            else:
                h2_n[0] += 1
                story.append(Paragraph(inline(f"{h1_n[0]}.{h2_n[0]} {htext}"), st["h2"]))
            continue
        if line.strip() in {r"\newpage", r"\pagebreak"}:
            flush_para(); story.append(PageBreak()); continue
        if not line.strip():
            flush_para(); continue
        para.append(line)

    flush_para(); flush_table()

    refs = sorted(((k, bib[k]) for k in used if k in bib), key=lambda kv: cite_label(kv[1]).lower())
    if refs:
        story.append(Paragraph("References", st["h1"]))
        for key, e in refs:
            story.append(Paragraph(f'<a name="cite-{key}"/>' + inline(full_reference(e)), st["ref"]))

    doc.build(story)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("qmd", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--bib", type=Path, default=None)
    args = parser.parse_args()
    build_pdf(args.qmd.resolve(), args.pdf.resolve(), args.bib.resolve() if args.bib else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
