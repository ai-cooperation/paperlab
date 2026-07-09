"""paper_meta.json v1 schema: strict at the boundary, prose refused by name."""
from __future__ import annotations

import json
from pathlib import Path

from engine_v3.assembly.metadata_schema import (
    PAPER_META_FILE,
    load_paper_meta,
    validate_paper_meta,
)


def _valid_meta() -> dict:
    return {
        "schema_version": "paper_meta.v1",
        "layout": "paper",
        "title": "A Study",
        "authors": [{"name": "Cooperation.TW", "email": "paperlab@cooperation.tw"}],
        "abstract_ref": "sections/00_abstract.md",
        "bibliography": "references.bib",
        "section_order": ["sections/introduction.md", "sections/methods.md"],
        "keywords": ["meta-analysis"],
    }


def test_valid_meta_passes() -> None:
    assert validate_paper_meta(_valid_meta()) == []


def test_missing_required_key_named_in_finding() -> None:
    meta = _valid_meta()
    del meta["abstract_ref"]
    findings = validate_paper_meta(meta)
    assert any("abstract_ref" in f for f in findings)


def test_abstract_prose_key_rejected_by_name() -> None:
    meta = _valid_meta()
    meta["abstract"] = "Long prose that must not live in JSON."
    findings = validate_paper_meta(meta)
    assert any("abstract PROSE" in f for f in findings)


def test_unknown_key_rejected() -> None:
    meta = _valid_meta()
    meta["surprise"] = 1
    assert any("unknown key 'surprise'" in f for f in validate_paper_meta(meta))


def test_bad_section_path_rejected() -> None:
    meta = _valid_meta()
    meta["section_order"] = ["notes/intro.md"]
    assert any("section_order[0]" in f for f in validate_paper_meta(meta))


def test_duplicate_section_rejected() -> None:
    meta = _valid_meta()
    meta["section_order"] = ["sections/introduction.md", "sections/introduction.md"]
    assert any("duplicates" in f for f in validate_paper_meta(meta))


def test_abstract_ref_must_not_be_in_section_order() -> None:
    meta = _valid_meta()
    meta["section_order"].append(meta["abstract_ref"])
    assert any("exactly once" in f for f in validate_paper_meta(meta))


def test_bad_layout_rejected() -> None:
    meta = _valid_meta()
    meta["layout"] = "poster"
    assert any("layout" in f for f in validate_paper_meta(meta))


def test_load_paper_meta_roundtrip(tmp_path: Path) -> None:
    (tmp_path / PAPER_META_FILE).write_text(json.dumps(_valid_meta()), encoding="utf-8")
    meta, findings = load_paper_meta(tmp_path)
    assert findings == []
    assert meta is not None and meta["title"] == "A Study"


def test_load_paper_meta_missing(tmp_path: Path) -> None:
    meta, findings = load_paper_meta(tmp_path)
    assert meta is None
    assert any("missing" in f for f in findings)


def test_load_paper_meta_invalid_json(tmp_path: Path) -> None:
    (tmp_path / PAPER_META_FILE).write_text("{not json", encoding="utf-8")
    meta, findings = load_paper_meta(tmp_path)
    assert meta is None
    assert any("unreadable" in f for f in findings)
