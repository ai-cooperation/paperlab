"""Freshness manifest: two hash sets, every render input covered, legacy exempt."""
from __future__ import annotations

import json
from pathlib import Path

from engine_v3.assembly import (
    RENDER_MANIFEST_FILE,
    assembly_source_files,
    freshness_findings,
    is_delivery_stale,
    render_source_files,
    write_render_manifest,
)
from engine_v3.assembly.manifest import assembly_source_sha256, render_source_sha256

from test_assembly_assembler import make_run


def _finish_render(run: Path) -> None:
    """Simulate a completed render: bib/contract/results/figures + PDF + manifest."""
    (run / "references.bib").write_text("@article{k1, author={A}, year={2024}}", encoding="utf-8")
    (run / "research_contract.json").write_text(json.dumps({"topic": "t"}), encoding="utf-8")
    (run / "real_experiments").mkdir(exist_ok=True)
    (run / "real_experiments" / "real_results.json").write_text("{}", encoding="utf-8")
    (run / "figures").mkdir(exist_ok=True)
    (run / "figures" / "fig1.png").write_bytes(b"\x89PNG-fake")
    (run / "paper_draft_v0.pdf").write_bytes(b"%PDF-1.4 fake")
    write_render_manifest(run)


def test_legacy_run_exempt(tmp_path: Path) -> None:
    assert assembly_source_files(tmp_path) is None
    assert render_source_files(tmp_path) is None
    assert freshness_findings(tmp_path) == []
    assert is_delivery_stale(tmp_path) is False


def test_render_set_is_superset_of_assembly_set(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    assembly = assembly_source_files(run)
    render = render_source_files(run)
    assert assembly is not None and render is not None
    assert set(assembly) < set(render)
    # every reviewed-out missing input is in the render set (V4-B enumeration)
    assert "references.bib" in render
    assert "research_contract.json" in render
    assert "real_experiments/real_results.json" in render


def test_figures_included_in_render_set(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "figures").mkdir()
    (run / "figures" / "forest.png").write_bytes(b"png")
    assert "figures/forest.png" in (render_source_files(run) or [])


def test_missing_manifest_is_a_finding(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    findings = freshness_findings(run)
    assert any(RENDER_MANIFEST_FILE in f for f in findings)
    assert is_delivery_stale(run)


def test_fresh_after_render_manifest(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    _finish_render(run)
    assert freshness_findings(run) == []
    assert not is_delivery_stale(run)


def test_section_edit_flips_staleness(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    _finish_render(run)
    (run / "sections" / "part1.md").write_text("## P\n\n" + "edited. " * 100, encoding="utf-8")
    assert is_delivery_stale(run)
    assert any("stale" in f for f in freshness_findings(run))


def test_bib_edit_flips_staleness(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    _finish_render(run)
    (run / "references.bib").write_text("@article{k2, author={B}, year={2025}}", encoding="utf-8")
    assert is_delivery_stale(run)


def test_real_results_edit_flips_staleness(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    _finish_render(run)
    (run / "real_experiments" / "real_results.json").write_text('{"n": 2}', encoding="utf-8")
    assert is_delivery_stale(run)


def test_contract_edit_flips_staleness(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    _finish_render(run)
    (run / "research_contract.json").write_text(json.dumps({"topic": "changed"}), encoding="utf-8")
    assert is_delivery_stale(run)


def test_figure_edit_flips_staleness_but_not_assembly_hash(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    _finish_render(run)
    before_assembly = assembly_source_sha256(run)
    (run / "figures" / "fig1.png").write_bytes(b"\x89PNG-different")
    assert is_delivery_stale(run)  # render set moved
    assert assembly_source_sha256(run) == before_assembly  # assembly set did NOT (V4-C split)


def test_missing_pdf_with_manifest_is_a_finding(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    _finish_render(run)
    (run / "paper_draft_v0.pdf").unlink()
    assert any("paper_draft_v0.pdf" in f for f in freshness_findings(run))


def test_render_hash_stable_across_double_manifest(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    _finish_render(run)
    first = render_source_sha256(run)
    write_render_manifest(run)  # re-render with unchanged sources
    assert render_source_sha256(run) == first
    assert freshness_findings(run) == []
