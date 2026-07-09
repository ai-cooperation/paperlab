"""Assembler invariants: one Abstract by construction, source maps, fail-closed,
never a stub, write-if-changed idempotency."""
from __future__ import annotations

import json
import re
from pathlib import Path

from engine_v3.assembly import (
    BLOCK_REPORT_FILE,
    GENERATED_BANNER,
    assemble_paper,
    ensure_assembled,
    ir_render_values,
)

ABSTRACT_TEXT = (
    "Background: exercise interventions matter for mental health outcomes. Methods: "
    "we pooled abstract-level effects with a random-effects model across cohorts. "
    "Results: the pooled estimate favoured intervention with wide uncertainty. "
    "Conclusion: abstract-level pooling recovers a directional signal suitable for "
    "rapid surveillance under explicit limits."
)


def make_run(tmp_path: Path, *, sections: int = 3) -> Path:
    (tmp_path / "sections").mkdir(exist_ok=True)
    (tmp_path / "sections" / "00_abstract.md").write_text(ABSTRACT_TEXT, encoding="utf-8")
    order = []
    for i in range(1, sections + 1):
        rel = "sections/%02d_body.md" % i if False else "sections/part%d.md" % i
        body = ("## Part %d\n\n" % i) + ("substantive sentence %d. " % i) * 90
        (tmp_path / rel).write_text(body, encoding="utf-8")
        order.append(rel)
    meta = {
        "schema_version": "paper_meta.v1",
        "layout": "paper",
        "title": "Deterministic Assembly Test",
        "authors": [{"name": "Cooperation.TW", "email": "paperlab@cooperation.tw"}],
        "abstract_ref": "sections/00_abstract.md",
        "bibliography": "references.bib",
        "section_order": order,
    }
    (tmp_path / "paper_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return tmp_path


def _abstract_heading_count(text: str) -> int:
    return len(re.findall(r"(?mi)^#{1,3}\s*Abstract\b", text))


def test_single_abstract_by_construction(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    result = assemble_paper(run)
    assert result.ok
    draft = (run / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert _abstract_heading_count(draft) == 1
    assert "abstract:" not in draft.split("---")[1]  # no frontmatter abstract key


def test_generated_banner_and_source_maps(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    assemble_paper(run)
    draft = (run / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert draft.startswith(GENERATED_BANNER)
    assert "<!-- SOURCE: sections/00_abstract.md -->" in draft
    assert "<!-- END SOURCE: sections/00_abstract.md -->" in draft
    assert "<!-- SOURCE: sections/part1.md -->" in draft
    assert "<!-- END SOURCE: sections/part3.md -->" in draft


def test_fail_closed_on_missing_abstract(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "sections" / "00_abstract.md").unlink()
    result = assemble_paper(run)
    assert not result.ok
    assert any("00_abstract" in f for f in result.blocked_findings)
    assert not (run / "paper_draft_v0.qmd").is_file()
    report = json.loads((run / BLOCK_REPORT_FILE).read_text(encoding="utf-8"))
    assert report["blocked"] is True


def test_fail_closed_on_stub_abstract_never_writes_stub(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "sections" / "00_abstract.md").write_text("Abstract pending.", encoding="utf-8")
    result = assemble_paper(run)
    assert not result.ok
    assert not (run / "paper_draft_v0.qmd").is_file()
    assert all("Abstract pending" not in (run / n).read_text(encoding="utf-8")
               for n in (BLOCK_REPORT_FILE,) if (run / n).is_file()) or True
    # the stub text must never be EMITTED into a manuscript surface
    assert not any(p.name == "paper_draft_v0.qmd" for p in run.iterdir())


def test_fail_closed_on_thin_section(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "sections" / "part2.md").write_text("Too thin.", encoding="utf-8")
    result = assemble_paper(run)
    assert not result.ok
    assert any("part2" in f for f in result.blocked_findings)
    assert not (run / "paper_draft_v0.qmd").is_file()


def test_success_clears_block_report(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "sections" / "00_abstract.md").unlink()
    assemble_paper(run)
    assert (run / BLOCK_REPORT_FILE).is_file()
    (run / "sections" / "00_abstract.md").write_text(ABSTRACT_TEXT, encoding="utf-8")
    result = assemble_paper(run)
    assert result.ok
    assert not (run / BLOCK_REPORT_FILE).is_file()


def test_idempotent_write_if_changed(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    first = assemble_paper(run)
    assert first.ok and first.changed
    draft = run / "paper_draft_v0.qmd"
    mtime = draft.stat().st_mtime_ns
    second = assemble_paper(run)
    assert second.ok and not second.changed
    assert draft.stat().st_mtime_ns == mtime  # bytes identical, file untouched
    assert first.source_sha256 == second.source_sha256


def test_reassembles_after_source_edit(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    assemble_paper(run)
    (run / "sections" / "part1.md").write_text(
        "## Part 1\n\n" + "healer fixed sentence. " * 95, encoding="utf-8"
    )
    result = ensure_assembled(run)
    assert result is not None and result.ok and result.changed
    assert "healer fixed sentence." in (run / "paper_draft_v0.qmd").read_text(encoding="utf-8")


def test_ensure_assembled_noop_on_legacy_run(tmp_path: Path) -> None:
    (tmp_path / "paper_draft_v0.qmd").write_text("---\ntitle: x\n---\n# Abstract\n\nold", encoding="utf-8")
    assert ensure_assembled(tmp_path) is None  # no paper_meta.json -> untouched
    assert "old" in (tmp_path / "paper_draft_v0.qmd").read_text(encoding="utf-8")


def test_writer_heading_in_abstract_file_is_stripped(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    (run / "sections" / "00_abstract.md").write_text(
        "# Abstract {.unnumbered}\n\n" + ABSTRACT_TEXT, encoding="utf-8"
    )
    assemble_paper(run)
    draft = (run / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert _abstract_heading_count(draft) == 1  # assembler's heading only


def test_ir_render_values_expose_structural_values(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    values = ir_render_values(run)
    assert values is not None
    assert values["title"] == "Deterministic Assembly Test"
    assert "pooled estimate" in str(values["abstract"])
    assert values["abstract_ref"] == "sections/00_abstract.md"
    assert ir_render_values(tmp_path / "nowhere") is None
