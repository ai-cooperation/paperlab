#!/usr/bin/env python3
"""Springer-style (Scientometrics) ReportLab renderer for paper-draft QMD output.

Used as the pipeline's deterministic render step when Quarto/LaTeX are unavailable
(ac-2012 has only reportlab). Unlike the old plain-text fallback, this parses the
YAML frontmatter, resolves @-citations against references.bib, numbers sections,
lays out booktabs tables, captions figures, and appends a hanging bibliography —
producing a publication-shaped manuscript rather than a text dump.

Dependency-free beyond reportlab (no yaml / bibtexparser). Every parser degrades
gracefully (e.g. an unparseable citation key is left as-is) rather than crashing.

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
from reportlab.platypus import (
    Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

NO_NUMBER_HEADINGS = {"abstract", "references", "keywords", "acknowledgements", "acknowledgments"}


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------
def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_text, body_text). Empty frontmatter if absent."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[3:end], text[nl + 1 :] if nl != -1 else ""
    return "", text


def parse_frontmatter(fm: str) -> dict[str, object]:
    """Targeted (non-YAML) parse of the fields we render."""
    meta: dict[str, object] = {"authors": []}

    def unquote(v: str) -> str:
        return v.strip().strip('"').strip("'").strip()

    lines = fm.splitlines()
    cur_author: dict[str, str] | None = None
    in_authors = False
    for line in lines:
        m_title = re.match(r"^title:\s*(.+)$", line)
        m_date = re.match(r"^date:\s*(.+)$", line)
        m_bib = re.match(r"^bibliography:\s*(.+)$", line)
        m_kw = re.match(r"^keywords:\s*(.+)$", line)
        if m_title:
            meta["title"] = unquote(m_title.group(1))
            in_authors = False
        elif m_date:
            meta["date"] = unquote(m_date.group(1))
            in_authors = False
        elif m_bib:
            meta["bibliography"] = unquote(m_bib.group(1))
            in_authors = False
        elif m_kw and m_kw.group(1).strip() not in {"", "|"}:
            meta["keywords"] = unquote(m_kw.group(1))
            in_authors = False
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
            elif re.match(r"^\S", line):  # dedent => authors block ended
                in_authors = False
    return meta


# ---------------------------------------------------------------------------
# BibTeX (references.bib)
# ---------------------------------------------------------------------------
def parse_bib(bib_path: Path) -> dict[str, dict[str, str]]:
    if not bib_path.is_file():
        return {}
    text = bib_path.read_text(encoding="utf-8", errors="ignore")
    entries: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"@\w+\s*\{\s*([^,]+),(.*?)\n\}", text, re.DOTALL):
        key = m.group(1).strip()
        body = m.group(2)
        fields: dict[str, str] = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}\s*,?\s*$", body, re.MULTILINE):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        if key:
            entries[key] = fields
    return entries


def _authors(entry: dict[str, str]) -> list[tuple[str, str]]:
    """Return [(last, firsts)] from a bib author field."""
    raw = entry.get("author", "")
    out: list[tuple[str, str]] = []
    for part in re.split(r"\s+and\s+", raw):
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
    """Author part of an in-text author-year citation."""
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
    auths = _authors(entry)
    def initials(first: str) -> str:
        return "".join(p[0].upper() for p in re.split(r"[\s.-]+", first) if p)
    names = ", ".join(f"{last} {initials(first)}".strip() for last, first in auths) or "Anon"
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
# In-text citations
# ---------------------------------------------------------------------------
def replace_citations(text: str, bib: dict[str, dict[str, str]], used: set[str]) -> str:
    def render_keys(keys: list[str], narrative: bool) -> str:
        parts: list[str] = []
        for k in keys:
            k = k.lstrip("@").strip()
            if k in bib:
                used.add(k)
                parts.append(cite_narrative(bib[k]) if narrative and len(keys) == 1 else cite_label(bib[k]))
            else:
                parts.append(k)
        if narrative and len(keys) == 1:
            return parts[0]
        return "(" + "; ".join(parts) + ")"

    # bracketed groups: [@a], [@a; @b], [@a, @b] (any bracket containing @keys)
    def repl_bracket(m: re.Match) -> str:
        keys = re.findall(r"@([A-Za-z0-9_:-]+)", m.group(0))
        return render_keys(keys, narrative=False) if keys else m.group(0)

    text = re.sub(r"\[[^\]]*@[A-Za-z][^\]]*\]", repl_bracket, text)
    # bare narrative @key (not preceded by [ or word char, e.g. emails handled in frontmatter)
    text = re.sub(
        r"(?<![\w\[@])@([A-Za-z][A-Za-z0-9_:-]+)",
        lambda m: render_keys([m.group(1)], narrative=True),
        text,
    )
    return text


# ---------------------------------------------------------------------------
# Inline markdown -> reportlab markup
# ---------------------------------------------------------------------------
def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^)]+)\)", r"\1", text)  # leftover md links
    return text


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def styles() -> dict[str, ParagraphStyle]:
    s = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=s["Title"], fontName="Helvetica-Bold",
                                 fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=10),
        "authors": ParagraphStyle("authors", parent=s["Normal"], fontSize=11, leading=14,
                                   alignment=TA_CENTER, spaceAfter=2),
        "affil": ParagraphStyle("affil", parent=s["Normal"], fontSize=9, leading=12,
                                 alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=12),
        "abstract": ParagraphStyle("abstract", parent=s["Normal"], fontSize=8.8, leading=11.5,
                                    alignment=TA_JUSTIFY, leftIndent=24, rightIndent=24, spaceAfter=6),
        "keywords": ParagraphStyle("keywords", parent=s["Normal"], fontSize=8.8, leading=11.5,
                                   leftIndent=24, rightIndent=24, spaceAfter=12),
        "h1": ParagraphStyle("h1", parent=s["Heading1"], fontName="Helvetica-Bold",
                             fontSize=12, leading=15, spaceBefore=10, spaceAfter=5),
        "h2": ParagraphStyle("h2", parent=s["Heading2"], fontName="Helvetica-Bold",
                             fontSize=10.5, leading=13, spaceBefore=7, spaceAfter=4),
        "body": ParagraphStyle("body", parent=s["BodyText"], fontName="Times-Roman",
                               fontSize=10, leading=13, alignment=TA_JUSTIFY, spaceAfter=5),
        "caption": ParagraphStyle("caption", parent=s["Normal"], fontSize=8.5, leading=11,
                                  alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
        "tcaption": ParagraphStyle("tcaption", parent=s["Normal"], fontName="Helvetica-Bold",
                                   fontSize=8.8, leading=11, spaceBefore=8, spaceAfter=3),
        "cell": ParagraphStyle("cell", parent=s["Normal"], fontName="Times-Roman", fontSize=8.5, leading=10.5),
        "cellh": ParagraphStyle("cellh", parent=s["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10.5),
        "ref": ParagraphStyle("ref", parent=s["Normal"], fontName="Times-Roman", fontSize=8.8, leading=11.5,
                              leftIndent=14, firstLineIndent=-14, spaceAfter=3),
    }


def title_block(story: list, meta: dict, st: dict) -> None:
    story.append(Paragraph(inline(str(meta.get("title") or "Untitled")), st["title"]))
    authors = meta.get("authors") or []
    if authors:
        names = ", ".join(str(a.get("name", "")) for a in authors)  # type: ignore[union-attr]
        story.append(Paragraph(inline(names), st["authors"]))
        affil = authors[0].get("affiliation", "")  # type: ignore[union-attr]
        email = authors[0].get("email", "")  # type: ignore[union-attr]
        sub = affil + (f" · {email}" if email else "")
        if sub:
            story.append(Paragraph(inline(sub), st["affil"]))
    if meta.get("date"):
        story.append(Paragraph(inline(str(meta["date"])), st["affil"]))


def make_table(rows: list[str], st: dict, counter: list[int]) -> list:
    grid = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    grid = [g for i, g in enumerate(grid) if not re.match(r"^[-:\s|]+$", "|".join(g))]
    if not grid:
        return []
    header, *data = grid
    table_data = [[Paragraph(inline(c), st["cellh"]) for c in header]] + [
        [Paragraph(inline(c), st["cell"]) for c in r] for r in data
    ]
    counter[0] += 1
    tbl = Table(table_data, hAlign="CENTER", repeatRows=1)
    tbl.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1.1, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.1, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [Paragraph(f"<b>Table {counter[0]}</b>", st["tcaption"]), tbl, Spacer(1, 8)]


def build_pdf(qmd: Path, pdf: Path, bib_path: Path | None = None) -> None:
    text = qmd.read_text(encoding="utf-8", errors="ignore")
    fm, body = split_frontmatter(text)
    meta = parse_frontmatter(fm)
    bib_file = bib_path or (qmd.parent / str(meta.get("bibliography") or "references.bib"))
    bib = parse_bib(bib_file)
    used_keys: set[str] = set()
    st = styles()

    doc = SimpleDocTemplate(
        str(pdf), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=str(meta.get("title") or qmd.stem),
    )
    story: list = []
    title_block(story, meta, st)
    if meta.get("keywords"):
        pass  # keywords rendered right after abstract below

    fig_n = [0]
    tbl_n = [0]
    h1_n, h2_n = [0], [0]
    para: list[str] = []
    table_block: list[str] = []
    in_code = False
    section_ctx = {"name": ""}

    def flush_para() -> None:
        if para:
            joined = " ".join(p.strip() for p in para if p.strip())
            if joined:
                joined = replace_citations(joined, bib, used_keys)
                style = st["abstract"] if section_ctx["name"] == "abstract" else st["body"]
                story.append(Paragraph(inline(joined), style))
            para.clear()

    def flush_table() -> None:
        if table_block:
            story.extend(make_table(table_block, st, tbl_n))
            table_block.clear()

    for raw in body.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            flush_para(); flush_table()
            in_code = not in_code
            continue
        if in_code:
            continue

        fig = re.match(r"^!\[(.*?)\]\(([^)]+)\)", line)
        if fig:
            flush_para(); flush_table()
            rel = fig.group(2).split("#", 1)[0].strip()
            img = (qmd.parent / rel).resolve()
            if img.is_file() and rel.lower().endswith((".png", ".jpg", ".jpeg")):
                fig_n[0] += 1
                story.append(Image(str(img), width=5.6 * inch, height=3.5 * inch, kind="proportional"))
                cap = replace_citations(fig.group(1), bib, used_keys)
                story.append(Paragraph(f"<b>Fig. {fig_n[0]}</b> {inline(cap)}", st["caption"]))
            continue

        if line.startswith("|") and line.rstrip().endswith("|"):
            flush_para()
            table_block.append(line)
            continue
        if table_block:
            flush_table()

        heading = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading:
            flush_para()
            level = len(heading.group(1))
            htext = heading.group(2).strip()
            key = htext.lower().strip()
            section_ctx["name"] = key
            if level == 1:
                if key in NO_NUMBER_HEADINGS:
                    label = htext
                else:
                    h1_n[0] += 1; h2_n[0] = 0
                    label = f"{h1_n[0]} {htext}"
                story.append(Paragraph(inline(label), st["h1"]))
                if key == "abstract":
                    pass
            else:
                h2_n[0] += 1
                label = f"{h1_n[0]}.{h2_n[0]} {htext}"
                story.append(Paragraph(inline(label), st["h2"]))
            # inject keywords right after the abstract heading's content later
            continue

        if line.strip() in {r"\newpage", r"\pagebreak"}:
            flush_para(); story.append(PageBreak()); continue
        if not line.strip():
            flush_para()
            # keywords printed once, right after abstract block ends
            if section_ctx["name"] == "abstract" and meta.get("keywords") and "kw_done" not in section_ctx:
                story.append(Paragraph(f"<b>Keywords</b> {inline(str(meta['keywords']))}", st["keywords"]))
                section_ctx["kw_done"] = "1"  # type: ignore[assignment]
            continue
        para.append(line)

    flush_para(); flush_table()

    # Bibliography (hanging indent, alphabetical) from cited keys
    refs = sorted((bib[k] for k in used_keys if k in bib), key=lambda e: cite_label(e).lower())
    if refs:
        story.append(Paragraph("References", st["h1"]))
        for e in refs:
            story.append(Paragraph(inline(full_reference(e)), st["ref"]))

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
