"""The render log is a DERIVED artifact (ADR-001 V2-C): judging a STALE log
manufactures unfixable pending findings.

v3_4dc73d199e17 circular deadlock (2026-07-15): the texttt-preamble fix was
deployed, making the delivery stale (renderer fingerprint changed) — but the
OLD render log still carried 3 Overfull findings. _validate_render_log_overflow
read it unconditionally -> pending content findings -> Gate R blocked
review_heal -> format_repair (the only phase that re-renders and refreshes the
log) never ran -> the log never refreshed. The healer cannot fix a finding that
describes a render which will be replaced anyway.

Rule: judge the log ONLY when the delivery is fresh. A stale delivery means
format_repair will re-render; Gate Z then judges the FRESH log, so nothing
ships unjudged (fail-closed preserved).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3 import assembly as engine_assembly
from engine_v3.pipelines import paper

pytestmark = pytest.mark.unit

OVERFULL_LOG = (
    "some tex noise\n"
    "Overfull \\hbox (49.5pt too wide) in paragraph at lines 521--531\n"
    "Overfull \\hbox (8.4pt too wide) in paragraph at lines 521--531\n"
)


def test_stale_delivery_suppresses_old_log_findings(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "paper_springer.log").write_text(OVERFULL_LOG, encoding="utf-8")
    monkeypatch.setattr(engine_assembly, "is_delivery_stale", lambda run_dir: True)
    out = paper._validate_render_log_overflow(tmp_path)
    assert out["valid"] is True
    assert out["findings"] == []
    assert out.get("log_stale") is True


def test_fresh_delivery_still_judges_the_log(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "paper_springer.log").write_text(OVERFULL_LOG, encoding="utf-8")
    monkeypatch.setattr(engine_assembly, "is_delivery_stale", lambda run_dir: False)
    out = paper._validate_render_log_overflow(tmp_path)
    assert out["valid"] is False
    assert out["overfull_count"] == 2  # 1.83pt-style sub-threshold noise absent here


def test_freshness_error_fails_closed_to_judging(tmp_path: Path, monkeypatch) -> None:
    """If freshness is undecidable, keep the old behavior (judge the log)."""
    (tmp_path / "paper_springer.log").write_text(OVERFULL_LOG, encoding="utf-8")

    def boom(run_dir):
        raise RuntimeError("manifest unreadable")

    monkeypatch.setattr(engine_assembly, "is_delivery_stale", boom)
    out = paper._validate_render_log_overflow(tmp_path)
    assert out["valid"] is False
    assert out["overfull_count"] == 2


def test_missing_log_unchanged(tmp_path: Path) -> None:
    out = paper._validate_render_log_overflow(tmp_path)
    assert out["valid"] is True and out["log_present"] is False
