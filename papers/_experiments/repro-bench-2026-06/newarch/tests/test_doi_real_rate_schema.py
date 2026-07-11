"""Regression: DOI real-rate recomputation must honour the audit producer's own
field spellings, not a stale/parallel checklist of field names that never existed.

Origin: job v3_72f87c735de5 — 46 references, every DOI verified against both
Crossref and OpenAlex (audit self-reports doi_real_rate=1.0), yet the engine
recomputed the rate as 0.0 and Gate A false-killed the job. Root cause: the
row-level recount (`_row_two_source_verified`) and the pipeline gate reader
(`_doi_real_rate`) each checked field names the producer never writes, so every
row scored False / the rate read as None. The recount is meant to catch a *stale*
top-level rate; it must not be *more brittle* than the producer it double-checks.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from engine_v3.artifacts.data import _canonical_references, _row_two_source_verified

pytestmark = pytest.mark.unit


# A row shaped exactly as the DOI-audit producer writes it (flat booleans + list +
# numeric tally + flat verdict) — the real producer truth for job v3_72f87c735de5.
_AUDIT_SHAPE_VERIFIED_ROW = {
    "doi": "10.1000/example",
    "title": "A Verified Reference",
    "crossref_ok": True,
    "openalex_ok": True,
    "two_source_verified": True,
    "sources_verified": ["Crossref", "OpenAlex"],
    "verification_sources_passed": 2,
}

# A genuinely unverified row: neither live source resolved. Must stay False so the
# fail-closed behaviour is not broken by the widened checklist.
_UNVERIFIED_ROW = {
    "doi": "10.1000/missing",
    "title": "An Unverified Reference",
    "crossref_ok": False,
    "openalex_ok": False,
    "two_source_verified": False,
    "sources_verified": [],
    "verification_sources_passed": 0,
}


def test_row_two_source_verified_accepts_audit_producer_shape() -> None:
    assert _row_two_source_verified(_AUDIT_SHAPE_VERIFIED_ROW) is True


def test_row_two_source_verified_flat_booleans_alone_suffice() -> None:
    # Only the flat per-source booleans present (no list, no tally, no flat verdict).
    row = {"crossref_ok": True, "openalex_ok": True}
    assert _row_two_source_verified(row) is True


def test_row_two_source_verified_sources_verified_list_alone_suffices() -> None:
    # Only the producer's `sources_verified` list present (distinct from the older
    # `verification_sources` spelling the checklist already knew).
    row = {"sources_verified": ["Crossref", "OpenAlex"]}
    assert _row_two_source_verified(row) is True


def test_row_two_source_verified_still_fails_closed_on_unverified() -> None:
    assert _row_two_source_verified(_UNVERIFIED_ROW) is False


def test_row_two_source_verified_single_source_fails_closed() -> None:
    # Exactly one live source resolved — not enough for the two-source rule.
    row = {"crossref_ok": True, "openalex_ok": False, "verification_sources_passed": 1}
    assert _row_two_source_verified(row) is False


def test_canonical_references_recomputes_full_rate_for_audit_shape() -> None:
    # The end-to-end path that Gate A depends on: producer says every row is
    # two-source verified; the row-recount must confirm 1.0, not 0.0.
    audit = {
        "doi_real_rate": 1.0,
        "records": [dict(_AUDIT_SHAPE_VERIFIED_ROW) for _ in range(46)],
    }
    result = _canonical_references(audit, references_bib="")
    assert result["two_source_rate"] == pytest.approx(1.0)
    assert result["count"] == 46


def test_canonical_references_rate_reflects_partial_verification() -> None:
    # Mixed corpus: half verified, half not — the recount must yield the true 0.5,
    # proving the widened checklist did not blanket-pass everything.
    records = [dict(_AUDIT_SHAPE_VERIFIED_ROW) for _ in range(3)]
    records += [dict(_UNVERIFIED_ROW) for _ in range(3)]
    audit = {"records": records}
    result = _canonical_references(audit, references_bib="")
    assert result["two_source_rate"] == pytest.approx(0.5)


def test_pipeline_doi_real_rate_reads_producer_key(tmp_path: Path) -> None:
    # `_doi_real_rate` must fall back across the producer's key spellings; the audit
    # for v3_72f87c735de5 has `doi_real_rate` (not the legacy `real_rate`) and must
    # read 1.0, not None (None fail-closes Gate A).
    pipeline = pytest.importorskip(
        "packs.paper.pipeline",
        reason="pipeline pulls matplotlib via meta_figures; skip where unavailable",
    )
    (tmp_path / "doi_audit.json").write_text('{"doi_real_rate": 1.0}', encoding="utf-8")
    assert pipeline._doi_real_rate(tmp_path) == pytest.approx(1.0)


def test_pipeline_doi_real_rate_legacy_key_still_read(tmp_path: Path) -> None:
    pipeline = pytest.importorskip("packs.paper.pipeline")
    (tmp_path / "doi_audit.json").write_text('{"real_rate": 0.9}', encoding="utf-8")
    assert pipeline._doi_real_rate(tmp_path) == pytest.approx(0.9)


def test_pipeline_doi_real_rate_absent_fails_closed(tmp_path: Path) -> None:
    # No rate under any known key — must return None so Gate A fail-closes.
    pipeline = pytest.importorskip("packs.paper.pipeline")
    (tmp_path / "doi_audit.json").write_text('{"kept": 46}', encoding="utf-8")
    assert pipeline._doi_real_rate(tmp_path) is None
