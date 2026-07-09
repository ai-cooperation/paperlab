"""Legacy migration: reconstruct sources from a model-authored qmd, fail-closed on
unrecoverable/stub abstracts, preserve nested headings as section body."""
from __future__ import annotations

import json
import re
from pathlib import Path

from engine_v3.assembly import PAPER_META_FILE, migrate_legacy_run

GOOD_ABSTRACT = (
    "Background: exercise interventions are widely studied for depressive symptoms. "
    "Methods: we pooled abstract-level standardized mean differences using a "
    "DerSimonian-Laird random-effects model. Results: the pooled estimate favoured "
    "exercise with substantial heterogeneity across cohorts. Conclusion: the signal "
    "is directionally informative for rapid surveillance under explicit limits."
)


def _legacy_qmd(abstract_marker: str = "# Abstract") -> str:
    body_para = "Substantive prose sentence for the migrated section. " * 30
    return (
        "---\n"
        'title: "Legacy Exercise Meta-Analysis"\n'
        "author:\n  - name: Cooperation.TW\n"
        "bibliography: references.bib\n"
        "---\n\n"
        f"{abstract_marker}\n\n{GOOD_ABSTRACT}\n\n"
        f"# Introduction\n\n{body_para}\n\n"
        f"# Methodology\n\n{body_para}\n\n"
        f"## Statistical Analysis\n\nNested subsection prose. {body_para}\n\n"
        f"# Conclusion\n\n{body_para}\n\n"
        "# References\n"
    )


def test_migrates_heading_abstract_to_sources(tmp_path: Path) -> None:
    (tmp_path / "paper_draft_v0.qmd").write_text(_legacy_qmd(), encoding="utf-8")
    result = migrate_legacy_run(tmp_path)
    assert result.ok, result.blocked_findings
    meta = json.loads((tmp_path / PAPER_META_FILE).read_text(encoding="utf-8"))
    assert meta["title"] == "Legacy Exercise Meta-Analysis"
    abstract = (tmp_path / "sections" / "00_abstract.md").read_text(encoding="utf-8")
    assert "DerSimonian-Laird" in abstract
    draft = (tmp_path / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert len(re.findall(r"(?m)^#{1,3}\s*Abstract\b", draft)) == 1
    assert len(re.findall(r"(?m)^#{1,3}\s*References\b", draft)) == 1  # no doubled refs heading


def test_migrates_pandoc_attr_and_bold_markers(tmp_path: Path) -> None:
    for marker in ("# Abstract {.unnumbered}", "**Abstract**"):
        run = tmp_path / marker.replace(" ", "_").replace("*", "b").replace("{", "").replace("}", "").replace(".", "")
        run.mkdir()
        (run / "paper_draft_v0.qmd").write_text(_legacy_qmd(marker), encoding="utf-8")
        result = migrate_legacy_run(run)
        assert result.ok, (marker, result.blocked_findings)


def test_nested_subheadings_stay_inside_their_section(tmp_path: Path) -> None:
    (tmp_path / "paper_draft_v0.qmd").write_text(_legacy_qmd(), encoding="utf-8")
    migrate_legacy_run(tmp_path)
    methodology = next((tmp_path / "sections").glob("*methodology*"))
    text = methodology.read_text(encoding="utf-8")
    assert "## Statistical Analysis" in text  # nested heading preserved as body


def test_fail_closed_on_stub_abstract(tmp_path: Path) -> None:
    qmd = _legacy_qmd().replace(GOOD_ABSTRACT, "Abstract pending.")
    (tmp_path / "paper_draft_v0.qmd").write_text(qmd, encoding="utf-8")
    result = migrate_legacy_run(tmp_path)
    assert not result.ok
    assert not (tmp_path / PAPER_META_FILE).is_file()
    assert any("abstract" in f.lower() for f in result.blocked_findings)


def test_fail_closed_on_missing_abstract(tmp_path: Path) -> None:
    qmd = "---\ntitle: x\n---\n\n# Introduction\n\n" + "prose. " * 120
    (tmp_path / "paper_draft_v0.qmd").write_text(qmd, encoding="utf-8")
    result = migrate_legacy_run(tmp_path)
    assert not result.ok


def test_reuses_existing_substantive_flat_sections(tmp_path: Path) -> None:
    (tmp_path / "paper_draft_v0.qmd").write_text(_legacy_qmd(), encoding="utf-8")
    (tmp_path / "sections").mkdir()
    for name in ("introduction", "related_work", "methods", "results", "discussion", "limitations", "conclusion"):
        (tmp_path / "sections" / ("%s.md" % name)).write_text(
            "## %s\n\n" % name.title() + "hermes prose. " * 90, encoding="utf-8"
        )
    result = migrate_legacy_run(tmp_path)
    assert result.ok
    meta = json.loads((tmp_path / PAPER_META_FILE).read_text(encoding="utf-8"))
    assert meta["section_order"][0] == "sections/introduction.md"  # reused, not re-split
    draft = (tmp_path / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert "hermes prose." in draft


def test_idempotent_after_migration(tmp_path: Path) -> None:
    (tmp_path / "paper_draft_v0.qmd").write_text(_legacy_qmd(), encoding="utf-8")
    assert migrate_legacy_run(tmp_path).ok
    second = migrate_legacy_run(tmp_path)  # meta exists -> plain assemble
    assert second.ok and not second.changed
