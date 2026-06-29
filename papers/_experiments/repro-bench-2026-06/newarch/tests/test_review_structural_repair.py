from __future__ import annotations

import re
from pathlib import Path

import pytest

from review_structural_repair import ABSTRACT_PLACEHOLDER, repair_run

pytestmark = pytest.mark.unit


def test_repair_run_adds_bib_abstracts_claim_audit_and_link_frontmatter(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "references.bib").write_text(
        "@article{A,\n  title={A},\n  doi={10.1000/a}\n}\n"
        "@article{B,\n  title={B},\n  doi={10.1000/b},\n  abstract={Existing abstract}\n}\n",
        encoding="utf-8",
    )
    (run_dir / "claim_evidence_map.md").write_text(
        "| ID | Quantitative claim | Evidence source | Support status |\n"
        "|---|---|---|---|\n"
        "| Q1 | The retained bibliography contains 41 verified references. | real_results.json verified_reference_count=41 | Supported |\n",
        encoding="utf-8",
    )
    for rel in ("paper_draft_v0.qmd", "paper_springer.qmd"):
        (run_dir / rel).write_text("---\ntitle: Test\n---\n\n# Body\n", encoding="utf-8")

    result = repair_run(run_dir)

    assert result["status"] == "changed"
    bib = (run_dir / "references.bib").read_text(encoding="utf-8")
    assert len(re.findall(r"(?im)^\s*abstract\s*=", bib)) == 2
    assert ABSTRACT_PLACEHOLDER in bib
    claim_map = (run_dir / "claim_evidence_map.md").read_text(encoding="utf-8")
    assert "V3.2 exact-match audit addendum" in claim_map
    assert "Exact Match" in claim_map
    assert "N Support" in claim_map
    assert "Numeric support present: 41" in claim_map
    qmd = (run_dir / "paper_springer.qmd").read_text(encoding="utf-8")
    assert "colorlinks: true" in qmd
    assert "citecolor: blue" in qmd
    assert (run_dir / "artifacts" / "manual_structural_repair").is_dir()


def test_repair_run_is_idempotent_after_structural_repairs(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "references.bib").write_text(
        "@article{A,\n  title={A},\n  abstract={Already present}\n}\n",
        encoding="utf-8",
    )
    (run_dir / "claim_evidence_map.md").write_text(
        "| Claim | Evidence | Source file | Validity | Exact Match | N Support | Attribution Verb |\n"
        "|---|---|---|---|---|---|---|\n"
        "| C | E | S | V | X | N | A |\n",
        encoding="utf-8",
    )
    (run_dir / "paper_draft_v0.qmd").write_text(
        "---\ntitle: Test\ncolorlinks: true\nlink-citations: true\ncitecolor: blue\nlinkcolor: blue\nurlcolor: blue\n---\n",
        encoding="utf-8",
    )
    (run_dir / "paper_springer.qmd").write_text((run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8"), encoding="utf-8")

    result = repair_run(run_dir)

    assert result == {"changed": [], "status": "unchanged"}
