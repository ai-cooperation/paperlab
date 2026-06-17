"""Phase 9b: the render-quality verify stage (format_repair.py).

Minimal and convergent: render the PDF, verify figure cross-references resolve, re-render
at most ONCE. Quarto is unavailable offline, so render + the crossref read are stubbed to
drive the control flow; the end-to-end render proof runs on ac-2012.
"""
from __future__ import annotations

import pytest

import format_repair

pytestmark = pytest.mark.unit


def test_broken_crossrefs_scoped_to_crossref_id(tmp_path, monkeypatch):
    monkeypatch.setattr(format_repair.revision_tasks, "render_quality_check",
                        lambda rd: [{"id": "RQ_CROSSREF"}, {"id": "RQ_MATH"}, {"id": "RQ_CITELINKS"}])
    ids = [d["id"] for d in format_repair.broken_crossrefs(tmp_path)]
    assert ids == ["RQ_CROSSREF"]                              # only the crossref fact is owned here


def test_verify_clean_is_noop_no_repair(tmp_path, monkeypatch):
    monkeypatch.setattr(format_repair, "render", lambda rd, c: True)
    monkeypatch.setattr(format_repair, "broken_crossrefs", lambda rd: [])
    res = format_repair.verify_and_repair(tmp_path, {})
    assert res["crossref_ok"] is True and res["repaired"] is False and res["before"] == []
    assert (tmp_path / "format_repair.json").is_file()


def test_verify_repairs_at_most_once(tmp_path, monkeypatch):
    renders = {"n": 0}

    def fake_render(rd, c):
        renders["n"] += 1
        return True

    # broken on the first read, resolved after the single re-render
    seq = [[{"id": "RQ_CROSSREF"}], []]
    monkeypatch.setattr(format_repair, "render", fake_render)
    monkeypatch.setattr(format_repair, "broken_crossrefs", lambda rd: seq.pop(0) if seq else [])

    res = format_repair.verify_and_repair(tmp_path, {})
    assert res["before"] == ["RQ_CROSSREF"] and res["crossref_ok"] is True and res["repaired"] is True
    assert renders["n"] == 2                                   # initial render + ONE repair render — no more


def test_verify_does_not_loop_when_unresolved(tmp_path, monkeypatch):
    renders = {"n": 0}

    def fake_render(rd, c):
        renders["n"] += 1
        return True

    monkeypatch.setattr(format_repair, "render", fake_render)
    monkeypatch.setattr(format_repair, "broken_crossrefs", lambda rd: [{"id": "RQ_CROSSREF"}])  # never clears

    res = format_repair.verify_and_repair(tmp_path, {})
    assert res["crossref_ok"] is False and res["remaining"] == ["RQ_CROSSREF"]
    assert renders["n"] == 2                                   # convergent: at most one repair, then report
