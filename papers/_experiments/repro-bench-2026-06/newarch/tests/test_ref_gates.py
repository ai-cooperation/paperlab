"""Reference-floor + citation-integrity delivery gates (skill Layers 1 & 2)."""
from __future__ import annotations

import json
from pathlib import Path

import delivery_audit as D


def _seed(run_dir: Path, *, lane: str, n_refs: int, cited: list[str] | None = None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "real_experiments").mkdir(exist_ok=True)
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps({"lane": lane}), encoding="utf-8")
    keys = [f"ref{i}" for i in range(n_refs)]
    (run_dir / "references.bib").write_text(
        "\n".join(f"@article{{{k},\n author={{A}},\n title={{T}},\n year={{2020}}\n}}" for k in keys),
        encoding="utf-8")
    (run_dir / "metadata.json").write_text(
        json.dumps([{"key": k, "status": "crossref_real"} for k in keys]), encoding="utf-8")
    body = "# Paper\n\n" + " ".join(f"see @{k}" for k in (cited if cited is not None else keys))
    (run_dir / "paper_draft_v0.qmd").write_text(body, encoding="utf-8")


def test_ref_floor_dataset_lane_blocks_below_35(tmp_path):
    _seed(tmp_path, lane="dataset_agent_analysis", n_refs=14)
    rr = {"lane": "dataset_agent_analysis"}
    issues = D._refs_count_check(tmp_path, rr)
    assert any(i["id"] == "D1_REFS_TOO_FEW" and i["severity"] == "P0" for i in issues)


def test_ref_floor_dataset_lane_passes_at_35(tmp_path):
    _seed(tmp_path, lane="dataset_agent_analysis", n_refs=35)
    assert D._refs_count_check(tmp_path, {"lane": "dataset_agent_analysis"}) == []


def test_ref_floor_meta_still_20(tmp_path):
    _seed(tmp_path, lane="meta_analysis", n_refs=18)
    assert any(i["id"] == "D1_REFS_TOO_FEW" for i in D._refs_count_check(tmp_path, {"lane": "meta_analysis"}))
    _seed(tmp_path, lane="meta_analysis", n_refs=22)
    assert D._refs_count_check(tmp_path, {"lane": "meta_analysis"}) == []


def test_ref_floor_ml_lane_exempt(tmp_path):
    _seed(tmp_path, lane="hupd_ml", n_refs=5)
    assert D._refs_count_check(tmp_path, {"lane": "hupd_ml"}) == []   # no floor for ML lane


def test_citation_integrity_all_verified_ok(tmp_path):
    _seed(tmp_path, lane="dataset_agent_analysis", n_refs=35)   # cites == verified keys
    assert D._citation_integrity_check(tmp_path) == []


def test_citation_integrity_unverified_blocks(tmp_path):
    # cite a key that is NOT in the verified bibliography (introduced after verification)
    _seed(tmp_path, lane="dataset_agent_analysis", n_refs=35,
          cited=["ref0", "ref1", "ghost_uncited_2024"])
    issues = D._citation_integrity_check(tmp_path)
    assert any(i["id"] == "D6_UNVERIFIED_CITATION" and i["severity"] == "P0" for i in issues)
    assert "ghost_uncited_2024" in issues[0]["keys"]


def test_citation_integrity_ignores_fig_tbl_refs(tmp_path):
    _seed(tmp_path, lane="dataset_agent_analysis", n_refs=35, cited=["ref0"])
    qmd = (tmp_path / "paper_draft_v0.qmd").read_text() + "\nSee @fig-forest, @tbl-main, @sec-intro."
    (tmp_path / "paper_draft_v0.qmd").write_text(qmd, encoding="utf-8")
    assert D._citation_integrity_check(tmp_path) == []   # crossrefs are not citations
