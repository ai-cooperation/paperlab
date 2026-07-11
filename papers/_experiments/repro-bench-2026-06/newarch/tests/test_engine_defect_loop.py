"""engine_defect classification loop: a delivery-surface block with clean
sources and no model repair route is the ENGINE's bug — record it with the
finding + engine fingerprint, stop retry loops from burning model rounds, and
requalify automatically when the engine code changes.

Origin: v3_aebc70c41043 (2026-07-11) burned its entire auto-retry budget (2
attempts) plus review_heal brain rounds on the assembler source-map paragraph
bug — a defect no model could ever fix because it lived outside the healer's
writable set while every source-level validator passed.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3 import assembly as engine_assembly
from engine_v3.core.contracts import Dossier, GateReport, GateResult, GateSeverity, PhaseSpec
from engine_v3.core.orchestrator import (
    ENGINE_DEFECT_FILE,
    _clear_engine_defect,
    _maybe_record_engine_defect,
)
from engine_v3.pipelines import paper

pytestmark = pytest.mark.unit


def _z_block() -> GateReport:
    return GateReport(
        results=[
            GateResult(
                gate_id="Z",
                passed=False,
                severity=GateSeverity.BLOCK,
                details="PDF contains unresolved citation/cross-reference markers",
                evidence={"artifact": "paper_draft_v0.pdf", "unresolved_markers": 1},
            )
        ]
    )


def _r_block() -> GateReport:
    return GateReport(
        results=[
            GateResult(gate_id="R", passed=False, severity=GateSeverity.BLOCK, details="review stale")
        ]
    )


# --- classifier -------------------------------------------------------------


def test_z_block_with_clean_sources_is_engine_defect(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / engine_assembly.PAPER_META_FILE).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paper, "_surface_pending_content_findings", lambda run_dir: [])
    info = paper._classify_format_repair_engine_defect(tmp_path, _z_block())
    assert info is not None
    assert info["class"] == "engine_defect"
    assert info["findings"][0]["details"].startswith("PDF contains unresolved")
    assert info["engine_fingerprint"]["assembler"] == engine_assembly.assembler_fingerprint()
    assert info["engine_fingerprint"]["renderer"] == engine_assembly.renderer_fingerprint()


def test_source_findings_present_means_healer_owns_it(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / engine_assembly.PAPER_META_FILE).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        paper, "_surface_pending_content_findings", lambda run_dir: ["dangling ref at source"]
    )
    assert paper._classify_format_repair_engine_defect(tmp_path, _z_block()) is None


def test_non_z_block_never_classified(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / engine_assembly.PAPER_META_FILE).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(paper, "_surface_pending_content_findings", lambda run_dir: [])
    assert paper._classify_format_repair_engine_defect(tmp_path, _r_block()) is None


def test_legacy_run_without_meta_never_classified(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(paper, "_surface_pending_content_findings", lambda run_dir: [])
    assert paper._classify_format_repair_engine_defect(tmp_path, _z_block()) is None


# --- orchestrator record/clear ----------------------------------------------


def _phase_with_classifier(classifier) -> PhaseSpec:
    return PhaseSpec(id="format_repair", handler=lambda task, ctx: {}, defect_classifier=classifier)


def test_orchestrator_records_marker_and_evidence(tmp_path: Path) -> None:
    dossier = Dossier(job_id="j", domain="paper")
    info = {"class": "engine_defect", "findings": [{"details": "x"}], "engine_fingerprint": {}}
    payload = _maybe_record_engine_defect(
        tmp_path, dossier, _phase_with_classifier(lambda run_dir, report: info), _z_block()
    )
    assert payload == info
    marker = json.loads((tmp_path / ENGINE_DEFECT_FILE).read_text(encoding="utf-8"))
    assert marker["class"] == "engine_defect"
    assert dossier.evidence["engine_defect"]["class"] == "engine_defect"


def test_orchestrator_clears_marker_when_phase_passes(tmp_path: Path) -> None:
    dossier = Dossier(job_id="j", domain="paper")
    (tmp_path / ENGINE_DEFECT_FILE).write_text("{}", encoding="utf-8")
    dossier.evidence["engine_defect"] = {"class": "engine_defect"}
    _clear_engine_defect(tmp_path, dossier, _phase_with_classifier(lambda run_dir, report: None))
    assert not (tmp_path / ENGINE_DEFECT_FILE).exists()
    assert "engine_defect" not in dossier.evidence


def test_classifier_exception_never_breaks_the_run(tmp_path: Path) -> None:
    dossier = Dossier(job_id="j", domain="paper")

    def boom(run_dir, report):
        raise RuntimeError("classifier bug")

    assert _maybe_record_engine_defect(tmp_path, dossier, _phase_with_classifier(boom), _z_block()) is None
    assert not (tmp_path / ENGINE_DEFECT_FILE).exists()


# --- auto-retry park/requalify ----------------------------------------------


def _defect_job(jobs: Path, jid: str, fingerprint: dict | str) -> None:
    run = jobs / jid / "run"
    run.mkdir(parents=True)
    (run / "dossier.v3.json").write_text(
        json.dumps({"phases": {"format_repair": "blocked"}}), encoding="utf-8"
    )
    (run / "engine_defect.json").write_text(
        json.dumps({"class": "engine_defect", "engine_fingerprint": fingerprint}), encoding="utf-8"
    )


def test_active_engine_defect_is_parked(tmp_path: Path) -> None:
    from auto_retry_v3 import select_retry_candidates

    current = {
        "assembler": engine_assembly.assembler_fingerprint(),
        "renderer": engine_assembly.renderer_fingerprint(),
    }
    _defect_job(tmp_path, "v3_parked", current)
    assert select_retry_candidates(tmp_path) == []


def test_fingerprint_drift_requalifies_even_past_budget(tmp_path: Path) -> None:
    """The deploy that fixes the engine is the retry trigger: a recorded
    fingerprint that no longer matches the running code reopens the job even
    after its 2-attempt budget was spent on the old defect."""
    from auto_retry_v3 import MAX_ATTEMPTS, select_retry_candidates

    _defect_job(tmp_path, "v3_drift", {"assembler": "old", "renderer": "old"})
    (tmp_path / "v3_drift" / "auto_retry.json").write_text(
        json.dumps({"attempts": MAX_ATTEMPTS, "last_attempt_ts": 0}), encoding="utf-8"
    )
    assert select_retry_candidates(tmp_path) == ["v3_drift"]


def test_marker_without_fingerprint_stays_parked(tmp_path: Path) -> None:
    from auto_retry_v3 import select_retry_candidates

    _defect_job(tmp_path, "v3_nofp", "not-a-dict")
    assert select_retry_candidates(tmp_path) == []
