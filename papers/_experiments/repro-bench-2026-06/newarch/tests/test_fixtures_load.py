"""Phase 0 GREEN bar (ENGINE_BUILD_PLAN.md): every build-plan fixture exists and
loads. These are not behaviour tests — they pin that the frozen inputs the later
phases depend on are present, well-formed, and shaped as the plan's table says.
"""
from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.fixtures, pytest.mark.unit]


# ── big real corpora (gzipped) ───────────────────────────────────────────────
@pytest.mark.parametrize("name", ["corpus_exercise.json", "corpus_mindfulness_thin.json"])
def test_corpus_loads_2400_works(load_fixture_json, name):
    data = load_fixture_json(name)
    assert isinstance(data, dict)
    works = data.get("works", data)
    assert isinstance(works, list)
    assert len(works) == 2400


def test_corpus_path_materialises_real_file(corpus_path):
    p = corpus_path("corpus_exercise.json")
    assert p.exists() and p.suffix == ".json"
    reloaded = json.loads(p.read_text(encoding="utf-8"))
    assert len(reloaded.get("works", reloaded)) == 2400


# ── golden_paper deterministic baseline ──────────────────────────────────────
GOLDEN_REQUIRED = [
    "research_contract.json",
    "references.bib",
    "metadata.json",
    "doi_audit.json",
    "gate_report.json",
    "final_content_review_deterministic.json",
    "reviewer_status.json",
    "paper_springer.qmd",
    "real_experiments/real_results.json",
]


@pytest.mark.parametrize("rel", GOLDEN_REQUIRED)
def test_golden_paper_has_artifact(golden_dir, rel):
    f = golden_dir / rel
    assert f.exists() and f.stat().st_size > 0, f"missing golden artifact: {rel}"


def test_golden_paper_json_artifacts_parse(golden_dir):
    for rel in GOLDEN_REQUIRED:
        if rel.endswith(".json"):
            json.loads((golden_dir / rel).read_text(encoding="utf-8"))


def test_golden_paper_has_four_source_figures(golden_dir):
    svgs = sorted((golden_dir / "figures").glob("*.svg"))
    assert {p.stem for p in svgs} == {
        "fig_method_overview", "fig_prisma_flow", "fig_forest_plot", "fig_benchmark_comparison",
    }


def test_golden_references_bib_nonempty(golden_dir):
    bib = (golden_dir / "references.bib").read_text(encoding="utf-8")
    assert bib.count("@") >= 30  # the run kept >=35 refs (refs>=35 floor)


# ── domain contracts (DomainPack interface seam, §2.2) ───────────────────────
CONTRACT_REQUIRED_KEYS = {"job_id", "source", "level", "topic", "research_question",
                          "contribution", "data_source"}


@pytest.mark.parametrize("name", [
    "contract_paper.json", "contract_insurance.json",
    "contract_ifrs.json", "contract_thin_handoff.json",
])
def test_contract_loads_with_envelope(load_fixture_json, name):
    c = load_fixture_json(name)
    assert isinstance(c, dict)
    assert CONTRACT_REQUIRED_KEYS <= set(c), f"{name} missing {CONTRACT_REQUIRED_KEYS - set(c)}"


def test_paper_contract_carries_picos(load_fixture_json):
    picos = load_fixture_json("contract_paper.json")["synthesis"]["picos"]
    assert picos["require_all"] and picos["require_any"]


def test_insurance_contract_carries_scope(load_fixture_json):
    scope = load_fixture_json("contract_insurance.json")["synthesis"]["scope"]
    assert {"region", "timeframe", "audience", "depth"} <= set(scope)


# ── gate fixtures ────────────────────────────────────────────────────────────
def test_overclaim_samples_present(fixtures_dir):
    txt = (fixtures_dir / "overclaim_samples.md").read_text(encoding="utf-8")
    assert txt.count("```claim") >= 6           # 5 listed + 1 planted unlisted
    assert "UNLISTED" in txt


def test_dup_figure_embeds_each_figure_twice(fixtures_dir):
    qmd = (fixtures_dir / "dup_figure.qmd").read_text(encoding="utf-8")
    assert qmd.count("figures/fig_method_overview.png") == 2
    assert qmd.count("figures/fig_forest_plot.png") == 2


def test_insurance_kb_small_findings_oracle(fixtures_dir):
    kb = fixtures_dir / "insurance_kb_small"
    docs = list((kb / "docs").glob("*.md"))
    assert len(docs) == 5
    oracle = json.loads((kb / "known_findings.json").read_text(encoding="utf-8"))
    assert len(oracle["findings"]) == 5
    assert oracle["expected"]["conflicting_pairs"] == [["f1", "f2"]]
    assert oracle["expected"]["stale_findings"] == ["f4"]


def test_insurance_gatefail_oracle(fixtures_dir):
    gf = fixtures_dir / "insurance_gatefail"
    assert (gf / "report.md").exists()
    oracle = json.loads((gf / "expected_gate_report.json").read_text(encoding="utf-8"))
    fired = {g["gate"] for g in oracle["gates"] if g["must_fire"]}
    assert {"body_too_thin", "footnote_orphan", "uncited_quantitative",
            "single_source_overreliance"} <= fired
    assert oracle["expected_block"] is True
