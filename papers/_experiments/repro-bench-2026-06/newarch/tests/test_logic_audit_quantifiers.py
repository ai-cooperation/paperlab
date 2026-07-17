"""Gate F quantifiers scan vs thousands separators.

Live false-kill (v3_e9f0eae7e200, 2026-07-17): the writer emitted evidence
numbers with thousands separators; NUMBER_PATTERN had no comma-group form, so
legal numbers like 365,049.852 were tokenized into fragments (365 / 049.852)
that can never trace back to the evidence JSON — a scanner-manufactured
UNFIXABLE finding (same family as the stale-render-log deadlock: the healer
burned 6 repair rounds against it). Contract pinned here:

- WELL-FORMED thousands-separated numbers match as one token and are
  normalized (commas stripped) before tracing against evidence.
- MALFORMED groupings (980510,598302 — groups not of three) stay flagged:
  that is a genuine manuscript defect, and it is now FIXABLE (reformat to
  -980,510,598,302 -> traces -> passes).
- Plain-number behavior is unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from packs.paper.logic_audit import scan_quantifiers

pytestmark = pytest.mark.unit


def _evidence(tmp_path: Path, payload: dict) -> str:
    fp = tmp_path / "real_results.json"
    fp.write_text(json.dumps(payload), encoding="utf-8")
    return str(fp)


def test_wellformed_thousands_number_traces_to_evidence(tmp_path: Path):
    fp = _evidence(tmp_path, {"mean_delta_twd": 365049.852})

    findings = scan_quantifiers(
        "TWSE listed firm-years have a mean delta of 365,049.852 TWD.", [fp]
    )

    assert findings == []


def test_wellformed_thousands_number_without_source_still_flagged(tmp_path: Path):
    fp = _evidence(tmp_path, {"mean_delta_twd": 111.0})

    findings = scan_quantifiers(
        "TWSE listed firm-years have a mean delta of 365,049.852 TWD.", [fp]
    )

    assert any(f["number"] == "365,049.852" and "NO_SOURCE" in f["verdict"] for f in findings)


def test_malformed_grouping_stays_flagged_but_is_healable(tmp_path: Path):
    fp = _evidence(tmp_path, {"total_after_tax_loss_thousand_twd": -980510598302})

    malformed = scan_quantifiers(
        "Across all firm-years, after-tax losses sum to -980510,598302 thousand TWD.", [fp]
    )
    healed = scan_quantifiers(
        "Across all firm-years, after-tax losses sum to -980,510,598,302 thousand TWD.", [fp]
    )

    assert malformed, "misplaced separators are a genuine manuscript defect"
    assert healed == [], "the healer must have a reachable pass state"


def test_plain_number_behavior_unchanged(tmp_path: Path):
    fp = _evidence(tmp_path, {"prr": 12.34})

    ok = scan_quantifiers("The PR improved by 12.34 after coating.", [fp])
    missing = scan_quantifiers("The PR improved by 56.78 after coating.", [fp])

    assert ok == []
    assert any(f["number"] == "56.78" for f in missing)
