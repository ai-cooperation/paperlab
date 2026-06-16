"""Shared gap-matrix parser (packs/paper/gaps.py) — must be GENERAL, not tuned to the
one English demo: English/Chinese headers, reordered columns, missing table, drift.
"""
from __future__ import annotations

import pytest

from packs.paper import gaps

pytestmark = pytest.mark.unit


def test_parses_english_gap_matrix():
    md = (
        "# Research Positioning\n\n## Gap Matrix\n\n"
        "| Gap | Description | Existing Work | Our Approach |\n"
        "|-----|-------------|---------------|--------------|\n"
        "| Evidence fragmentation | Reviews focus on single formats. | A; B | We pool all. |\n"
        "| Heterogeneity | Older adults differ. | C | We report I2. |\n\n"
        "## Differentiation Statement\nUnlike prior work...\n"
    )
    out = gaps.parse_gap_matrix(md)
    assert [g["gap"] for g in out] == ["Evidence fragmentation", "Heterogeneity"]
    assert out[0]["description"].startswith("Reviews focus")


def test_parses_chinese_gap_table_without_english_heading():
    md = (
        "## 研究定位\n\n"
        "| 缺口 | 說明 |\n|------|------|\n"
        "| 證據分散 | 既有回顧多聚焦單一形式 |\n"
        "| 族群異質 | 高齡者差異大 |\n"
    )
    out = gaps.parse_gap_matrix(md)
    assert [g["gap"] for g in out] == ["證據分散", "族群異質"]
    assert out[1]["description"] == "高齡者差異大"


def test_no_gap_table_returns_empty():
    assert gaps.parse_gap_matrix("# Title\n\nSome prose, no table at all.\n") == []
    assert gaps.parse_gap_matrix("") == []


def test_ignores_non_gap_tables():
    md = (
        "| Study | Effect |\n|---|---|\n| A | 0.3 |\n\n"
        "## Gap Matrix\n| Gap | Description |\n|---|---|\n| Real gap | desc |\n"
    )
    out = gaps.parse_gap_matrix(md)
    assert [g["gap"] for g in out] == ["Real gap"]


def test_caps_at_limit():
    rows = "\n".join(f"| G{i} | d{i} |" for i in range(20))
    md = "| Gap | Description |\n|---|---|\n" + rows
    assert len(gaps.parse_gap_matrix(md, limit=5)) == 5
