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
