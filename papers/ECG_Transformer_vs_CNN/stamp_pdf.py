#!/usr/bin/env python3
"""Add SHOWCASE watermark and footer to paper PDF using PyMuPDF."""

import fitz  # PyMuPDF
from pathlib import Path

SRC = Path(__file__).parent / "paper_draft_v0.pdf"
DST = Path(__file__).parent / "paper_draft_v0_showcase.pdf"

FOOTER = "paperlab.cooperation.tw  |  Showcase Draft  |  Paper Lab Methodology Demo"
FIRST_PAGE_BANNER = (
    "SHOWCASE DRAFT  —  Not for Submission  —  Methodology Demonstration Only"
)


def stamp():
    doc = fitz.open(str(SRC))

    for i, page in enumerate(doc):
        rect = page.rect
        w, h = rect.width, rect.height

        # Footer on every page (English only — PyMuPDF font limitation)
        footer_rect = fitz.Rect(40, h - 30, w - 40, h - 10)
        page.insert_textbox(
            footer_rect,
            FOOTER,
            fontsize=7,
            fontname="helv",
            color=(0.4, 0.4, 0.4),
            align=fitz.TEXT_ALIGN_CENTER,
        )

        # First page: prominent banner
        if i == 0:
            # Red banner box at top
            banner_rect = fitz.Rect(40, 15, w - 40, 38)
            page.draw_rect(banner_rect, color=(0.85, 0.15, 0.15), fill=(1, 0.95, 0.95))
            page.insert_textbox(
                fitz.Rect(42, 17, w - 42, 36),
                FIRST_PAGE_BANNER,
                fontsize=8.5,
                fontname="helv",
                color=(0.85, 0.15, 0.15),
                align=fitz.TEXT_ALIGN_CENTER,
            )

        # Horizontal watermark on every page (subtle, centered)
        wm_rect = fitz.Rect(w * 0.15, h * 0.42, w * 0.85, h * 0.52)
        page.insert_textbox(
            wm_rect, "SHOWCASE  DRAFT",
            fontsize=52, fontname="helv",
            color=(0.93, 0.93, 0.93),
            align=fitz.TEXT_ALIGN_CENTER,
        )

    doc.save(str(DST))
    doc.close()
    print(f"Stamped PDF: {DST} ({DST.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    stamp()
