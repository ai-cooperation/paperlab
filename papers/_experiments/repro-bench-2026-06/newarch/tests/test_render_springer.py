from __future__ import annotations

from pathlib import Path

import pytest

import render_springer

pytestmark = pytest.mark.unit


def test_normalize_frontmatter_removes_flattened_metadata_from_abstract_and_keywords(
    tmp_path: Path,
):
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "---\n"
        'title: "Weather Transfer Paper"\n'
        "abstract: |\n"
        "  Real abstract sentence about transfer learning.\n"
        "  keywords: - extreme weather - transfer learning - format:\n"
        "  format: pdf: documentclass: article number-sections: true\n"
        "keywords:\n"
        "  - extreme weather\n"
        "  - transfer learning\n"
        "  - format:\n"
        "format:\n"
        "  pdf:\n"
        "    number-sections: true\n"
        "    geometry:\n"
        "      - top=25mm\n"
        "bibliography: references.bib\n"
        "---\n\n"
        "# Introduction\n\n"
        "Body text.\n",
        encoding="utf-8",
    )

    out = render_springer.normalize_frontmatter(tmp_path, {}, out_name="paper_springer.qmd")

    text = out.read_text(encoding="utf-8")
    frontmatter = text.split("---", 2)[1]
    abstract_block = frontmatter.split("keywords:", 1)[0]
    keywords_block = frontmatter.split("keywords:", 1)[1].split("format:", 1)[0]

    assert "Real abstract sentence about transfer learning." in abstract_block
    assert "keywords:" not in abstract_block
    assert "format:" not in abstract_block
    assert "- extreme weather" in keywords_block
    assert "- transfer learning" in keywords_block
    assert "- format:" not in keywords_block
    assert "top=25mm" not in keywords_block


def test_extract_abstract_handles_unnumbered_heading_attribute():
    """Root cause of the 2026-07-07 double-Abstract breakout: the writer emits
    '# Abstract {.unnumbered}', but _extract_abstract's regex required the
    heading text to be followed directly by a newline, so the attribute block
    made it MISS the section. It then fell back to injecting 'Abstract
    pending.' into the frontmatter while leaving the real body Abstract in
    place -> two Abstracts in the rendered PDF (DTP3/ESG/e9e1 all carried
    '# Abstract {.unnumbered}')."""
    body = (
        "# Abstract {.unnumbered}\n\n"
        "This is the real abstract text describing the study.\n\n"
        "# Introduction\n\nBody prose.\n"
    )
    abstract, new_body, _kw = render_springer._extract_abstract("", body)
    assert "real abstract text" in abstract
    assert "Abstract pending" not in abstract
    # the body Abstract section must be REMOVED so it does not render twice
    assert "# Abstract" not in new_body
    assert "# Introduction" in new_body


def test_extract_abstract_still_handles_plain_heading():
    body = "## Abstract\n\nPlain-heading abstract.\n\n## Methods\n\nx\n"
    abstract, new_body, _kw = render_springer._extract_abstract("", body)
    assert "Plain-heading abstract" in abstract
    assert "Abstract" not in new_body.split("Methods")[0]


def test_extract_abstract_handles_bold_abstract_marker():
    """0deb (Transfer Learning) wrote the abstract as a bold '**Abstract**'
    line, not a '# Abstract' heading. _extract_abstract only matched '#'
    headings, so it missed the section, injected the 'Abstract pending.'
    stub into the frontmatter, and left the bold Abstract block in the body
    -> double Abstract. The abstract itself was complete and correct; only
    the marker style differed (same class as the {.unnumbered} variant)."""
    body = (
        "**Abstract**\n\n"
        "Data-driven weather foundation models have achieved strong skill, yet "
        "their transferability to rare events remains unresolved.\n\n"
        "**Keywords:** extreme weather; transfer learning\n\n"
        "# Introduction\n\nBody prose.\n"
    )
    abstract, new_body, kw = render_springer._extract_abstract("", body)
    assert "weather foundation models" in abstract
    assert "Abstract pending" not in abstract
    assert "**Abstract**" not in new_body
    assert "# Introduction" in new_body
    assert "extreme weather" in kw
