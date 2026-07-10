"""Bib-quality gates from the 2026-07-10 adversarial quality audit: placeholder
authors, placeholder abstracts, and DOI/year mismatch must fail closed — the DOI
existence audit reported real_rate=1.0 while these defects shipped to 3 papers."""
from __future__ import annotations

from pathlib import Path

import pytest

from engine_v3.pipelines.paper import (
    _validate_bib_author_integrity,
    _validate_bib_metadata_consistency,
    content_validators,
)
import review_structural_repair

pytestmark = pytest.mark.unit


def _bib(tmp_path: Path, entry: str) -> Path:
    (tmp_path / "references.bib").write_text(entry, encoding="utf-8")
    return tmp_path


# --- placeholder / broken authors (the defect) --------------------------------


def test_study_authors_placeholder_flagged(tmp_path: Path) -> None:
    r = _validate_bib_author_integrity(_bib(tmp_path, "@article{k, author = {Study authors}, year = {2024}}\n"))
    assert not r["valid"] and any("Study authors" in f for f in r["findings"])


def test_coauthors_fragment_flagged(tmp_path: Path) -> None:
    r = _validate_bib_author_integrity(_bib(tmp_path, "@article{k, author = {Hua, Z. and coauthors}, year = {2024}}\n"))
    assert not r["valid"]


# --- legitimate authors must NOT be flagged (false-positive guards) ------------


def test_standard_and_others_not_flagged(tmp_path: Path) -> None:
    """`and others` is standard BibTeX for et al. — GraphCast's real author list
    ending in 'and others' must pass (my first regex wrongly blocked it)."""
    r = _validate_bib_author_integrity(_bib(
        tmp_path, "@article{k, author = {Lam, Remi and Sanchez-Gonzalez, Alvaro and others}, year = {2023}}\n"))
    assert r["valid"], r["findings"]


def test_normal_authors_not_flagged(tmp_path: Path) -> None:
    r = _validate_bib_author_integrity(_bib(tmp_path, "@article{k, author = {Smith, John and Doe, Jane}, year = {2024}}\n"))
    assert r["valid"]


# --- placeholder abstract + DOI/year mismatch ---------------------------------


def test_placeholder_abstract_flagged(tmp_path: Path) -> None:
    r = _validate_bib_metadata_consistency(_bib(
        tmp_path, "@article{k, author = {A, B}, year = {2024},\n  abstract = {Abstract unavailable placeholder}}\n"))
    assert not r["valid"] and any("placeholder abstract" in f for f in r["findings"])


def test_doi_year_drift_not_flagged_online_first(tmp_path: Path) -> None:
    """A DOI-year vs pub-year gap is NOT gated: online-first legitimately differs by
    a year (golden_paper's liang2026 = year 2026 with a 2025 DOI). Gating it would
    false-positive on known-good papers, so the metadata gate ignores year drift."""
    r = _validate_bib_metadata_consistency(_bib(
        tmp_path, "@article{k, author = {A, B}, year = {2026}, doi = {10.3389/fphys.2025.1744254}}\n"))
    assert r["valid"]


def test_clean_bib_passes_both(tmp_path: Path) -> None:
    run = _bib(tmp_path, "@article{k, author = {Smith, John}, title = {T}, year = {2024}, journal = {J}, doi = {10.1/x.2024.1}}\n")
    assert _validate_bib_author_integrity(run)["valid"]
    assert _validate_bib_metadata_consistency(run)["valid"]


# --- both gates registered in the pipeline validator set ----------------------


def test_both_bib_gates_registered() -> None:
    names = {v.__name__ for v in content_validators()}
    assert "_validate_bib_author_integrity" in names
    assert "_validate_bib_metadata_consistency" in names


# --- structural repair NO LONGER injects abstract fields, and strips existing --


def test_structural_repair_strips_abstract_field(tmp_path: Path) -> None:
    bib = tmp_path / "references.bib"
    bib.write_text(
        "@article{k1,\n  author = {A, B},\n  year = {2024},\n"
        "  abstract = {some placeholder abstract text here},\n  journal = {J}\n}\n",
        encoding="utf-8",
    )
    changed = review_structural_repair._strip_bib_abstract_fields(bib)
    text = bib.read_text(encoding="utf-8")
    assert changed
    assert "abstract" not in text.lower()
    assert "author = {A, B}" in text and "journal = {J}" in text  # rest intact


def test_structural_repair_noop_when_no_abstract(tmp_path: Path) -> None:
    bib = tmp_path / "references.bib"
    bib.write_text("@article{k1,\n  author = {A, B},\n  year = {2024}\n}\n", encoding="utf-8")
    assert review_structural_repair._strip_bib_abstract_fields(bib) is False


# --- dangling crossref gate (fresh E2E v3_9e68543a8540: '?@fig-effects') -------

from engine_v3.pipelines.paper import _validate_figure_ref_targets


def test_dangling_fig_ref_flagged(tmp_path: Path) -> None:
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "---\ntitle: t\n---\n\nSee @fig-effects for details.\n\n"
        "![cap](figures/a.png){#fig-forest}\n",
        encoding="utf-8",
    )
    r = _validate_figure_ref_targets(tmp_path)
    assert not r["valid"]
    assert any("fig-effects" in f for f in r["findings"])


def test_labeled_and_generated_refs_not_flagged(tmp_path: Path) -> None:
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "---\ntitle: t\n---\n\nSee @fig-forest and @tbl-studies.\n\n"
        "![cap](figures/a.png){#fig-forest}\n\n"
        "<!-- GENERATED:tbl-studies source=real_results sha256=abc -->\n|a|\n<!-- /GENERATED:tbl-studies -->\n",
        encoding="utf-8",
    )
    r = _validate_figure_ref_targets(tmp_path)
    assert r["valid"], r["findings"]


def test_figure_ref_gate_registered() -> None:
    assert "_validate_figure_ref_targets" in {v.__name__ for v in content_validators()}


# --- injector must not clobber a healer's foreign-label embed (fresh E2E) ------


def test_inject_figures_normalizes_foreign_label_refs(tmp_path: Path) -> None:
    """v3_9e68543a8540: the healer embedded fig_forest_plot.png as {#fig-effects};
    the injector stripped it by filename and left @fig-effects dangling forever.
    Now the foreign refs are normalized to the canonical id before the strip, so
    the single canonical embed serves them."""
    import tables

    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "fig_forest_plot.png").write_bytes(b"png")
    (tmp_path / "paper_draft_v0.qmd").write_text(
        "---\ntitle: t\n---\n\n# Results\n\n"
        "The map in @fig-effects shows the estimates.\n\n"
        "![healer caption](figures/fig_forest_plot.png){#fig-effects width=85%}\n",
        encoding="utf-8",
    )
    tables.inject_figures(tmp_path, figspec=[("fig-forest", "fig_forest_plot.png", "Canonical caption.")])
    text = (tmp_path / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "@fig-effects" not in text          # foreign ref normalized
    assert "@fig-forest" in text               # ...to the canonical id
    assert text.count("{#fig-forest}") == 1    # exactly one canonical embed
    assert "{#fig-effects" not in text         # foreign embed gone (dedup preserved)
