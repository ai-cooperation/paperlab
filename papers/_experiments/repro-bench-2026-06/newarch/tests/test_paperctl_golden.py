"""Golden reproduction tests for the ``paperctl`` CLI (ENGINE_BUILD_PLAN Phase 2).

paperctl is a PURE WRAPPER over the deterministic engine core. These tests drive
it IN-PROCESS via ``paperctl.main([...])`` (no subprocess, so failures are
debuggable) and assert it reproduces the frozen ``tests/fixtures/golden_paper``
outputs. Everything runs OFFLINE:

* the meta-analysis lane reads a seeded ``run_dir/_corpus_cache.json`` (the frozen
  ``corpus_exercise.json``) instead of hitting OpenAlex;
* ``refs build-from-dois`` mocks ``doi_audit.fetch_crossref_meta`` from the frozen
  ``golden_paper/_crossref_metadata.json``;
* the network gates (data-availability, doi) mock their HTTP entry points.

See the module docstring of ``paperctl.py`` for the CLI surface.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from unittest import mock

import pytest

import paperctl

pytestmark = pytest.mark.integration

# Pooled k expected per the build plan (deterministic over the frozen corpus).
EXPECTED_POOLED_K = {"smd": 8, "log_ratio": 3}
POOLED_TOL = 1e-6


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _seed_corpus_cache(run_dir: Path, load_fixture_json) -> None:
    """Write the frozen exercise corpus as the run's ``_corpus_cache.json`` so the
    meta-analysis lane runs fully offline (it reuses the phase-0 collect cache)."""
    corpus = load_fixture_json("corpus_exercise.json")
    (run_dir / "_corpus_cache.json").write_text(
        json.dumps(corpus, ensure_ascii=False), encoding="utf-8")


def _copy_golden(name: str, golden_dir: Path, run_dir: Path) -> None:
    src = golden_dir / name
    dst = run_dir / name
    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy(src, dst)


def _copy_golden_tree(golden_dir: Path, run_dir: Path) -> None:
    """Materialise the whole golden run (minus internal mock fixtures) so the
    gates / review have every artifact they read."""
    skip = {"_crossref_metadata.json", "_key_map.json"}
    for item in golden_dir.iterdir():
        if item.name in skip:
            continue
        _copy_golden(item.name, golden_dir, run_dir)


def _fake_fetch_from_golden(golden_dir: Path):
    """A ``doi_audit.fetch_crossref_meta`` stand-in backed by the frozen CrossRef
    metadata. Returns ``("ok", {...list authors...})`` for a known DOI and
    ``("404", None)`` for anything absent (the fabricated-DOI drop path)."""
    meta = json.loads((golden_dir / "_crossref_metadata.json").read_text(encoding="utf-8"))

    def _fetch(doi: str, timeout: int = 8):
        m = meta.get(doi)
        if m is None:
            return ("404", None)
        authors = [a.strip() for a in str(m.get("authors", "")).split(" and ") if a.strip()]
        return ("ok", {
            "title": m.get("title", ""),
            "authors": authors,
            "year": str(m.get("year", "")),
            "journal": m.get("journal", ""),
        })

    return _fetch, meta


def _figure_embed_count(qmd: Path, fname: str) -> int:
    return len(re.findall(re.escape(f"(figures/{fname})"), qmd.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# 1. data meta-analysis reproduces pooled k + estimates/CIs EXACTLY
# --------------------------------------------------------------------------- #
def test_data_meta_analysis_reproduces_golden_pooled(tmp_path, golden_dir, load_fixture_json):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _seed_corpus_cache(run_dir, load_fixture_json)
    _copy_golden("research_contract.json", golden_dir, run_dir)

    rc = paperctl.main(["data", "meta-analysis", "--run-dir", str(run_dir)])
    assert rc == 0

    produced = json.loads(
        (run_dir / "real_experiments" / "real_results.json").read_text(encoding="utf-8"))
    assert produced["status"] == "completed"
    pooled = produced["meta"]["pooled"]

    # pooled k EXACTLY {smd:8, log_ratio:3}
    assert {s: pooled[s]["k"] for s in EXPECTED_POOLED_K} == EXPECTED_POOLED_K

    # pooled estimate + CI match the golden real_results within 1e-6 (deterministic).
    golden = json.loads(
        (golden_dir / "real_experiments" / "real_results.json").read_text(encoding="utf-8"))
    gold_pooled = golden["meta"]["pooled"]
    for scale in EXPECTED_POOLED_K:
        for field in ("pooled_effect", "ci_low", "ci_high"):
            assert pooled[scale][field] == pytest.approx(
                gold_pooled[scale][field], abs=POOLED_TOL), f"{scale}.{field}"


# --------------------------------------------------------------------------- #
# 2. tables inject — each figure embedded exactly ONCE; idempotent (2 -> 1 -> 1)
# --------------------------------------------------------------------------- #
def test_tables_inject_dedups_figures_idempotently(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    shutil.copy(golden_dir.parent / "dup_figure.qmd", run_dir / "paper_draft_v0.qmd")
    (run_dir / "figures").mkdir()
    for fname in ("fig_method_overview.png", "fig_forest_plot.png"):
        shutil.copy(golden_dir / "figures" / fname, run_dir / "figures" / fname)

    qmd = run_dir / "paper_draft_v0.qmd"
    # fixture starts with each figure embedded TWICE.
    assert _figure_embed_count(qmd, "fig_method_overview.png") == 2
    assert _figure_embed_count(qmd, "fig_forest_plot.png") == 2

    rc1 = paperctl.main(["tables", "inject", "--run-dir", str(run_dir)])
    assert rc1 == 0
    assert _figure_embed_count(qmd, "fig_method_overview.png") == 1  # 2 -> 1
    assert _figure_embed_count(qmd, "fig_forest_plot.png") == 1

    # running it again is idempotent (still exactly one each).
    rc2 = paperctl.main(["tables", "inject", "--run-dir", str(run_dir)])
    assert rc2 == 0
    assert _figure_embed_count(qmd, "fig_method_overview.png") == 1
    assert _figure_embed_count(qmd, "fig_forest_plot.png") == 1


# --------------------------------------------------------------------------- #
# 3. figures meta — forest / PRISMA / method, each as svg + png
# --------------------------------------------------------------------------- #
def test_figures_meta_produces_svg_png(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden("real_experiments", golden_dir, run_dir)

    rc = paperctl.main(["figures", "meta", "--run-dir", str(run_dir)])
    assert rc == 0

    figdir = run_dir / "figures"
    # meta_figures.generate() emits three figures (forest, PRISMA, method), each
    # as svg + png. (The build plan's "4 figures" includes the benchmark figure,
    # which is produced by a different lane; meta_figures owns exactly these 3.)
    for stem in ("fig_forest_plot", "fig_prisma_flow", "fig_method_overview"):
        for ext in (".svg", ".png"):
            f = figdir / f"{stem}{ext}"
            assert f.is_file() and f.stat().st_size > 0, f"missing {f.name}"


def test_figures_meta_produces_protocol_gap_prisma_svg_png(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "result_type": "audited-literature-and-protocol-gap-results",
                "verified_reference_count": 41,
                "crossref_verified_count": 41,
                "same_extreme_subset_benchmark_found": False,
                "poolable_same_subset_effect_k": 0,
            }
        ),
        encoding="utf-8",
    )

    rc = paperctl.main(["figures", "meta", "--run-dir", str(run_dir)])

    assert rc == 0
    for ext in (".svg", ".png"):
        f = run_dir / "figures" / f"fig_prisma_flow{ext}"
        assert f.is_file() and f.stat().st_size > 0, f"missing {f.name}"
    svg = (run_dir / "figures" / "fig_prisma_flow.svg").read_text(encoding="utf-8")
    assert "PRISMA-style data-phase evidence flow" in svg
    assert "weather foundation models" in svg


# --------------------------------------------------------------------------- #
# 4. provenance — provenance.json with the golden key shape
# --------------------------------------------------------------------------- #
def test_provenance_matches_golden_shape(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden("real_experiments", golden_dir, run_dir)
    _copy_golden("research_contract.json", golden_dir, run_dir)

    rc = paperctl.main(["provenance", "--run-dir", str(run_dir)])
    assert rc == 0

    prov = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    golden_prov = json.loads((golden_dir / "provenance.json").read_text(encoding="utf-8"))
    assert set(prov) == set(golden_prov)
    assert prov["schema_version"] == golden_prov["schema_version"]
    # content-hash of the (identical) real_results.json must reproduce byte-for-byte.
    assert prov["real_results_sha256"] == golden_prov["real_results_sha256"]
    assert prov["data_source"] == golden_prov["data_source"]
    assert prov["real_results_status"] == golden_prov["real_results_status"]


# --------------------------------------------------------------------------- #
# 5. refs build-from-dois — reproduces the golden doi_audit shape / real_rate
# --------------------------------------------------------------------------- #
def test_refs_build_from_dois_reproduces_audit_shape(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    fake_fetch, meta = _fake_fetch_from_golden(golden_dir)
    suspicious = "10.5281/zenodo.14200027"  # the golden fabricated DOI (CrossRef-404)
    assert suspicious not in meta  # must hit the drop path

    contract = {"literature": {"doi_list": list(meta.keys()) + [suspicious]}}
    (run_dir / "research_contract.json").write_text(
        json.dumps(contract, ensure_ascii=False), encoding="utf-8")

    import doi_audit
    with mock.patch.object(doi_audit, "fetch_crossref_meta", side_effect=fake_fetch), \
            mock.patch("time.sleep", lambda *_: None):
        rc = paperctl.main(["refs", "build-from-dois", "--run-dir", str(run_dir)])
    assert rc == 0

    audit = json.loads((run_dir / "doi_audit.json").read_text(encoding="utf-8"))
    golden = json.loads((golden_dir / "doi_audit.json").read_text(encoding="utf-8"))

    # same audit SHAPE as the golden run.
    assert set(audit) == set(golden)
    assert audit["mode"] == golden["mode"] == "verify_and_complete"
    # the fabricated DOI is dropped, real ones kept; real_rate computed + above floor.
    assert audit["suspicious_404"] == 1
    assert audit["suspicious_dois"] == [suspicious]
    assert audit["kept"] == len(meta)
    assert audit["real_rate"] == round(len(meta) / (len(meta) + 1), 3)
    assert audit["passed"] is True
    # references.bib built by construction (one @article per kept DOI).
    bib = (run_dir / "references.bib").read_text(encoding="utf-8")
    assert bib.count("@article{") == len(meta)


# --------------------------------------------------------------------------- #
# 5b. refs audit (doi_gate) — independent CrossRef re-verify, golden audit shape
# --------------------------------------------------------------------------- #
def test_refs_audit_doi_gate_returns_structured_verdict(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden("references.bib", golden_dir, run_dir)
    _copy_golden("metadata.json", golden_dir, run_dir)
    _copy_golden("doi_verification_report.md", golden_dir, run_dir)

    import doi_audit
    with mock.patch.object(doi_audit, "check_crossref", return_value=True), \
            mock.patch("time.sleep", lambda *_: None):
        rc = paperctl.main(["refs", "audit", "--run-dir", str(run_dir)])
    assert rc == 0

    audit = json.loads((run_dir / "doi_audit.json").read_text(encoding="utf-8"))
    assert audit["passed"] is True
    assert audit["real_existence_rate"] == 1.0  # all mocked as real
    assert audit["floor"] == 0.8


# --------------------------------------------------------------------------- #
# 6. each gate subcommand runs and returns a structured verdict + exit code
# --------------------------------------------------------------------------- #
def test_gate_phase2_doi(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden("references.bib", golden_dir, run_dir)
    _copy_golden("metadata.json", golden_dir, run_dir)
    _copy_golden("doi_verification_report.md", golden_dir, run_dir)

    import doi_audit
    with mock.patch.object(doi_audit, "check_crossref", return_value=True), \
            mock.patch("time.sleep", lambda *_: None):
        rc = paperctl.main(["gate", "phase2", "--run-dir", str(run_dir)])
    assert rc == 0
    audit = json.loads((run_dir / "doi_audit.json").read_text(encoding="utf-8"))
    assert audit["passed"] is True


def test_gate_phase3_consistency(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden_tree(golden_dir, run_dir)

    rc = paperctl.main(["gate", "phase3", "--run-dir", str(run_dir)])
    # literature lane -> no HUPD ground truth -> 0 consistency tasks -> passes.
    assert rc == 0


def test_gate_phase8_data_availability_blocks_offline(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden_tree(golden_dir, run_dir)

    import data_availability_gate
    with mock.patch.object(
            data_availability_gate, "head_status",
            side_effect=OSError("offline")):
        rc = paperctl.main(["gate", "phase8", "--run-dir", str(run_dir)])
    # offline -> the source-lock probe fails closed (structured verdict, blocks).
    assert rc == 1
    lock = json.loads((run_dir / "data_source_lock.json").read_text(encoding="utf-8"))
    assert lock["status"] == "unavailable"
    assert "reason" in lock


def test_gate_phase9_content_writes_gate_report(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden_tree(golden_dir, run_dir)

    rc = paperctl.main(["gate", "phase9", "--run-dir", str(run_dir)])
    # the golden draft carries known P0 render/consistency issues -> the gate
    # correctly BLOCKS (exit 1). The point is the structured verdict, reproduced.
    assert rc == 1
    gate_report = json.loads((run_dir / "gate_report.json").read_text(encoding="utf-8"))
    golden_report = json.loads((golden_dir / "gate_report.json").read_text(encoding="utf-8"))
    assert set(gate_report) == set(golden_report)
    # the deterministic content-score reproduces the frozen value exactly.
    assert gate_report["score_threshold"] == golden_report["score_threshold"]
    assert gate_report["p1_count"] == golden_report["p1_count"]
    assert gate_report["real_status"] == golden_report["real_status"]


def test_gate_final_content_verdict(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden_tree(golden_dir, run_dir)

    rc = paperctl.main(["gate", "final", "--run-dir", str(run_dir)])
    assert rc == 1  # same content backend as phase9; structured verdict, blocks.
    final = json.loads(
        (run_dir / "final_content_review_deterministic.json").read_text(encoding="utf-8"))
    assert "meets_threshold" in final
    assert final["meets_threshold"] is False


# --------------------------------------------------------------------------- #
# review compile — the deterministic content-review compile path
# --------------------------------------------------------------------------- #
def test_review_compile_reproduces_gate_report(tmp_path, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    _copy_golden_tree(golden_dir, run_dir)

    rc = paperctl.main(["review", "compile", "--run-dir", str(run_dir)])
    assert rc == 1  # golden draft does not meet threshold (known P0s).
    final = json.loads(
        (run_dir / "final_content_review_deterministic.json").read_text(encoding="utf-8"))
    assert final["mean_7dim"] == json.loads(
        (golden_dir / "gate_report.json").read_text(encoding="utf-8"))["score_threshold"]


# --------------------------------------------------------------------------- #
# CLI surface — help / unknown command behaviour (no crash, sane exit)
# --------------------------------------------------------------------------- #
def test_main_no_args_prints_help_exit_2(capsys):
    rc = paperctl.main([])
    assert rc == 2
    out = capsys.readouterr().out
    assert "paperctl" in out


def test_main_missing_run_dir_errors(tmp_path):
    missing = tmp_path / "nope"
    rc = paperctl.main(["provenance", "--run-dir", str(missing)])
    assert rc == 2
