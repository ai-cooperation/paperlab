"""Phase 4: the paper pack's hard-gates A–F as REAL checks (DESIGN §3.7–§3.8).

Each gate is pinned with a KNOWN-PASS and a KNOWN-FAIL using the frozen fixtures.
The gates are the PACK's ``gate_registry``; the FRAMEWORK's ``run_gates`` lifecycle
runs + enforces them (independent re-run), so most tests drive the gate THROUGH the
framework to prove the lifecycle wiring, not just the helper in isolation.

Fixtures used:
  overclaim_samples.md        — 5 listed overclaims + 1 planted UNLISTED (Gate B)
  dup_figure.qmd              — each figure embedded twice (Gate C)
  golden_paper/               — real run; the known-PASS substrate for A/C/D/E
  corpus_exercise.json.gz     — value-sufficient corpus (Gate E pass)
  corpus_mindfulness_thin.*   — value-insufficient (thin) corpus (Gate E warn)
  gates/good_draft.md         — coherent minimal draft (Gate B/F pass)
  gates/placeholder_draft.md  — placeholder + under-length (Gate D fail)
  gates/contradiction_draft.md— planted internal contradiction (Gate F fail)
"""
from __future__ import annotations

import gzip
import json
import re
import shutil
from pathlib import Path

import pytest

import synthesis
import tables
from framework import Severity, run_gates
from packs.paper import PaperPack
from packs.paper import gates as paper_gates

pytestmark = pytest.mark.unit

GOLDEN_REAL_RESULTS = {
    "meta": {"pooled": {"smd": {"k": 8, "pooled_effect": -0.4327, "i2_percent": 95.4}}}
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _run_one(dossier: dict, name: str):
    """Run a single named pack gate through the framework lifecycle; return its result."""
    report = run_gates(PaperPack(), dossier, only={name})
    assert report.results, f"gate {name} not registered"
    return report, report.results[0]


def _claim_evidence_blocks(fixtures_dir: Path) -> tuple[list[str], list[str]]:
    text = (fixtures_dir / "overclaim_samples.md").read_text(encoding="utf-8")
    claims = re.findall(r"```claim\n(.*?)\n```", text, re.DOTALL)
    evidence = re.findall(r"```evidence\n(.*?)\n```", text, re.DOTALL)
    return claims, evidence


# --------------------------------------------------------------------------- #
# Gate A — contract/refs (BLOCK): refs>=35 AND doi_real_rate>=0.80
# --------------------------------------------------------------------------- #
def test_gate_a_pass_meets_floors():
    dossier = {"evidence": {"references": {"bib_count": 47, "doi_real_rate": 0.979}}}
    report, res = _run_one(dossier, "A")
    assert res.passed is True and res.p0 is False and report.blocked is False


def test_gate_a_fail_below_floor_blocks():
    dossier = {"evidence": {"references": {"bib_count": 12, "doi_real_rate": 0.5}}}
    report, res = _run_one(dossier, "A")
    assert res.passed is False and res.p0 is True and report.blocked is True


def test_gate_a_fail_closed_on_missing_evidence():
    report, res = _run_one({}, "A")
    assert res.passed is False and res.p0 is True   # never a silent pass


# --------------------------------------------------------------------------- #
# Gate B — claim <= evidence (BLOCK, the spine): independent extraction
#   KNOWN-FAIL: every one of the 5 LISTED overclaims is P0, AND the planted
#   UNLISTED claim is ALSO caught by independent extraction (not just the listed).
# --------------------------------------------------------------------------- #
def test_gate_b_treats_epc_contract_guarantee_as_domain_term():
    claims = paper_gates.extract_claims(
        "Contract guarantees, profit sharing, and risk allocation depend on the "
        "credibility of the savings estimate."
    )

    assert claims == []


def test_gate_b_still_flags_general_guarantees_as_strong_claim():
    claims = paper_gates.extract_claims(
        "The intervention guarantees lower mortality across all settings."
    )

    assert claims and claims[0]["causal"] == "guarantees"


def test_gate_b_flags_all_listed_and_the_unlisted_overclaim(fixtures_dir):
    claims, evidence = _claim_evidence_blocks(fixtures_dir)
    assert len(claims) == 6 and len(evidence) == 6   # 5 listed + 1 unlisted

    # The DRAFT prose is the claim blocks; the agent-filled matrix is the EVIDENCE
    # (what is grounded). real_results carries only the modest grounded numbers.
    draft = "\n\n".join(claims)
    claim_evidence = [{"evidence": e} for e in evidence]
    real_results = {"configs": 24, "baselines": 2, "datasets": 1,
                    "benchmarks_measured": 1, "runs": 5}

    report, res = _run_one(
        {"draft_text": draft, "claim_evidence": claim_evidence, "real_results": real_results},
        "B")
    assert res.passed is False and res.p0 is True and report.blocked is True

    flagged = res.evidence["flagged"]
    flagged_text = " ||| ".join(f["claim"].lower() for f in flagged)

    # all 5 LISTED overclaims (distinctive token per sample) are flagged
    listed_markers = ["1,200", "at least 90%", "prove", "always", "first-line"]
    for marker in listed_markers:
        assert marker.lower() in flagged_text, f"listed overclaim not flagged: {marker}"

    # the UNLISTED planted claim ("every public leaderboard ...") is ALSO caught —
    # by independent extraction, NOT because it was in the listed set.
    unlisted = [f for f in flagged if "leaderboard" in f["claim"].lower()]
    assert unlisted, "planted UNLISTED overclaim was NOT caught by independent extraction"
    # and it was caught on its own merits (scope overreach / universal quantifier)
    reasons = " ".join(unlisted[0]["reasons"]).lower()
    assert "overreach" in reasons or "quantifier" in reasons


def test_gate_b_pass_when_number_matches_evidence(fixtures_dir):
    # A claim whose number/quantifier matches its evidence -> no P0.
    good = (fixtures_dir / "gates" / "good_draft.md").read_text(encoding="utf-8")
    claim_evidence = [{"row": "k=8 SMD pool (real_results smd k=8)"},
                      {"row": "pooled SMD -0.4327 (real_results pooled smd)"},
                      {"row": "I-squared 95.4 (real_results i2)"}]
    report, res = _run_one(
        {"draft_text": good, "claim_evidence": claim_evidence,
         "real_results": GOLDEN_REAL_RESULTS}, "B")
    assert res.passed is True and res.p0 is False, res.evidence.get("flagged")
    assert report.blocked is False


def test_gate_b_scientific_notation_p_value_matches_claim_evidence_row():
    draft = (
        "In the M4 adjusted model, the current-DTP3 row reports a coefficient of "
        "-0.234 (clustered SE 0.059, 95% CI [-0.350, -0.118], p = 7.618e-05)."
    )
    claim_evidence = [
        {
            "row": (
                "In the M4 adjusted model, the current-DTP3 row reports a coefficient of "
                "-0.234 (clustered SE 0.059, 95% CI [-0.350, -0.118], p = 7.618e-05). "
                "Evidence: real_results M4 current-DTP3 row."
            )
        }
    ]
    real_results = {
        "current_coef": -0.234,
        "current_se": 0.059,
        "current_ci": [-0.350, -0.118],
        "current_p": 7.618e-05,
    }

    report, res = _run_one(
        {"draft_text": draft, "claim_evidence": claim_evidence, "real_results": real_results},
        "B",
    )

    assert res.passed is True, res.evidence.get("flagged")
    assert report.blocked is False


def test_gate_b_allows_first_line_when_guideline_evidence_is_listed():
    draft = (
        "Cognitive behavioral therapy for insomnia is widely recommended as a "
        "first-line intervention by clinical guidance [@Morin2015; @Carney2017]."
    )
    claim_evidence = [
        {
            "row": (
                "first-line intervention | Morin2015 and Carney2017 clinical guidance "
                "support CBT-I as a first-line insomnia intervention"
            )
        }
    ]

    report, res = _run_one(
        {"draft_text": draft, "claim_evidence": claim_evidence, "real_results": {}},
        "B",
    )

    assert res.passed is True, res.evidence.get("flagged")
    assert res.p0 is False
    assert report.blocked is False


def test_gate_b_does_not_block_first_line_background_context():
    draft = (
        "Digital cognitive behavioral therapy for insomnia can expand access to "
        "first-line insomnia care, but the available evidence remains heterogeneous. "
        "Cognitive behavioral therapy for insomnia is widely recommended as a "
        "first-line intervention [@Morin2015]."
    )

    report, res = _run_one(
        {"draft_text": draft, "claim_evidence": [], "real_results": {}},
        "B",
    )

    assert res.passed is True, res.evidence.get("flagged")
    assert res.p0 is False
    assert report.blocked is False


def test_gate_b_does_not_block_negated_protocol_or_epistemic_scope_language():
    draft = (
        "The resulting research gap is not that Transformers have never been used for weather forecasting. "
        "The protocol requires identical train, validation, and test splits for every model family. "
        "The evidence includes studies questioning whether pretrained large time-series models consistently "
        "outperform smaller alternatives."
    )
    claim_evidence = [
        {"row": "research gap is bounded to same-subset protocol absence"},
        {"row": "protocol scope covers the model families evaluated in this benchmark"},
        {"row": "outperformance is framed as an open question, not as a finding"},
    ]

    report, res = _run_one(
        {"draft_text": draft, "claim_evidence": claim_evidence, "real_results": {}},
        "B",
    )

    assert res.passed is True, res.evidence.get("flagged")
    assert res.p0 is False
    assert report.blocked is False


def test_gate_b_does_not_treat_calendar_years_as_result_numbers():
    draft = (
        "A case study of the July 2021 Henan rainfall event traces the chain from weather "
        "forecast to climate risk, illustrating how event-specific processes and impact "
        "definitions can affect interpretation [@Wu2023]."
    )

    report, res = _run_one(
        {"draft_text": draft, "claim_evidence": [], "real_results": {}},
        "B",
    )

    assert res.passed is True, res.evidence.get("flagged")
    assert report.blocked is False


def test_gate_b_does_not_block_feasibility_summary_demonstrates_that_language():
    draft = (
        "The broader extreme-event modeling literature also demonstrates that event tasks "
        "are feasible but heterogeneous. This category demonstrates that deep learning can "
        "be applied to tropical cyclones, lightning, heatwaves, and precipitation correction."
    )
    claim_evidence = [
        {"row": "extreme-event modeling literature covers task feasibility and heterogeneity"},
        {"row": "task-specific studies show deep learning applications across event targets"},
    ]

    report, res = _run_one(
        {"draft_text": draft, "claim_evidence": claim_evidence, "real_results": {}},
        "B",
    )

    assert res.passed is True, res.evidence.get("flagged")
    assert report.blocked is False


def test_gate_b_fail_closed_without_draft():
    report, res = _run_one({"claim_evidence": [], "real_results": {}}, "B")
    assert res.passed is False and res.p0 is True
    assert "fail-closed" in res.details


# --------------------------------------------------------------------------- #
# Gate C — figure quality (BLOCK): SVG+PNG, numbers==real_results, dedup
#   KNOWN-FAIL: dup_figure.qmd embeds each figure twice -> gate detects duplication.
#   tables.inject_figures dedups 2->1 (idempotent) -> gate then passes (KNOWN-PASS).
# --------------------------------------------------------------------------- #
def test_gate_c_detects_duplicate_embeds_then_dedup_passes(tmp_path, fixtures_dir, golden_dir):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    shutil.copy(fixtures_dir / "dup_figure.qmd", run_dir / "paper_draft_v0.qmd")
    shutil.copytree(golden_dir / "figures", run_dir / "figures")

    figs = [{"name": p.stem, "svg": True, "png": True}
            for p in (run_dir / "figures").glob("*.png")]
    qmd_before = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")

    # BEFORE: each figure embedded twice -> Gate C detects the duplication and blocks
    report, res = _run_one(
        {"evidence": {"figures": figs}, "qmd_text": qmd_before,
         "real_results": GOLDEN_REAL_RESULTS}, "C")
    assert res.passed is False and report.blocked is True
    assert res.evidence["embed_counts"]["fig_method_overview.png"] == 2
    assert res.evidence["embed_counts"]["fig_forest_plot.png"] == 2

    # the real fix: inject_figures dedups 2 -> 1 and is idempotent on the embed count
    tables.inject_figures(run_dir)
    qmd_after = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    tables.inject_figures(run_dir)                       # idempotent
    qmd_after2 = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")

    def _count(text: str, fname: str) -> int:
        return len(re.findall(re.escape(f"(figures/{fname})"), text))

    for fname in ("fig_method_overview.png", "fig_forest_plot.png"):
        assert _count(qmd_after, fname) == 1
        assert _count(qmd_after2, fname) == 1            # idempotent (2 -> 1 -> 1)

    # AFTER: no duplicate embeds survive -> Gate C passes (KNOWN-PASS)
    _, res2 = _run_one(
        {"evidence": {"figures": figs}, "qmd_text": qmd_after,
         "real_results": GOLDEN_REAL_RESULTS}, "C")
    assert res2.passed is True and res2.p0 is False


def test_inject_figures_places_float_in_body_not_abstract(tmp_path):
    """Regression (live 2026-06-16): when a figure's FIRST @ref is in the abstract
    (## Abstract, before the first level-1 `# ` heading), its labelled float must STILL
    be placed in the BODY. A float in front matter renders as a broken ?@fig- because
    Quarto does not register crossref floats before the first level-1 heading (the real
    run produced 10 such broken markers: forest x6 + prisma x4)."""
    run_dir = tmp_path / "run"
    (run_dir / "figures").mkdir(parents=True)
    (run_dir / "figures" / "fig_forest_plot.png").write_bytes(b"")   # inject only checks existence
    qmd = (
        "---\ntitle: t\n---\n\n"
        "## Abstract\n\n"
        "The pooled estimate is summarized in @fig-forest.\n\n"      # FIRST ref: in the abstract
        "# Introduction\n\n"
        "The forest result is shown in @fig-forest.\n"               # body ref
    )
    (run_dir / "paper_draft_v0.qmd").write_text(qmd, encoding="utf-8")

    tables.inject_figures(run_dir)
    out = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")

    float_idx = out.find("{#fig-forest}")
    intro_idx = out.find("# Introduction")
    assert float_idx != -1, "float was not injected"
    assert float_idx > intro_idx, "float must be in the body, not the abstract/front matter"
    assert out.count("(figures/fig_forest_plot.png)") == 1           # exactly one embed (idempotent)

    tables.inject_figures(run_dir)                                   # idempotent: still body, still one
    out2 = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    assert out2.find("{#fig-forest}") > out2.find("# Introduction")
    assert out2.count("(figures/fig_forest_plot.png)") == 1


def test_inject_figures_normalizes_hyphenated_writer_aliases(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "figures").mkdir(parents=True)
    (run_dir / "figures" / "fig_forest_plot.png").write_bytes(b"")
    (run_dir / "figures" / "fig_prisma_flow.png").write_bytes(b"")
    (run_dir / "figures" / "fig_method_overview.png").write_bytes(b"")
    (run_dir / "paper_draft_v0.qmd").write_text(
        "# Introduction\n\n"
        "See @fig-method-overview and @fig-prisma-flow.\n\n"
        "# Results\n\n"
        "The evidence summary is shown in @fig-forest-plot.\n",
        encoding="utf-8",
    )

    tables.inject_figures(run_dir)
    out = (run_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")

    assert "@fig-method-overview" not in out
    assert "@fig-prisma-flow" not in out
    assert "@fig-forest-plot" not in out
    assert "@fig-method" in out
    assert "@fig-prisma" in out
    assert "@fig-forest" in out
    assert out.count("{#fig-method}") == 1
    assert out.count("{#fig-prisma}") == 1
    assert out.count("{#fig-forest}") == 1


def test_gate_c_pass_golden_figures(golden_dir):
    figs = [{"name": p.stem, "svg": True, "png": True}
            for p in (golden_dir / "figures").glob("*.png")]
    draft = (golden_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    _, res = _run_one({"evidence": {"figures": figs}, "qmd_text": draft,
                       "real_results": GOLDEN_REAL_RESULTS}, "C")
    assert res.passed is True and res.p0 is False


def test_gate_c_fail_closed_without_figures():
    _, res = _run_one({"evidence": {"figures": []}}, "C")
    assert res.passed is False and res.p0 is True


# --------------------------------------------------------------------------- #
# Gate D — readability/render (BLOCK): placeholder / under-length / render-fail
# --------------------------------------------------------------------------- #
def test_gate_d_fail_on_placeholder_and_underlength(fixtures_dir):
    draft = (fixtures_dir / "gates" / "placeholder_draft.md").read_text(encoding="utf-8")
    report, res = _run_one({"draft_text": draft}, "D")
    assert res.passed is False and res.p0 is True and report.blocked is True
    probs = " ".join(res.evidence["problems"]).lower()
    assert "placeholder" in probs and "too thin" in probs


def test_gate_d_fail_on_render_failure():
    long_clean = "Lorem-free academic prose. " * 700   # over the word floor, no markers
    report, res = _run_one({"draft_text": long_clean, "render_ok": False}, "D")
    assert res.passed is False and res.p0 is True
    assert "render failed" in " ".join(res.evidence["problems"]).lower()


def test_gate_d_pass_golden_draft(golden_dir):
    draft = (golden_dir / "paper_draft_v0.qmd").read_text(encoding="utf-8")
    report, res = _run_one({"draft_text": draft, "render_ok": True}, "D")
    assert res.passed is True and res.p0 is False and report.blocked is False
    assert res.evidence["words"] >= paper_gates.PROSE_WORD_FLOOR


def test_gate_d_fail_closed_without_draft():
    _, res = _run_one({}, "D")
    assert res.passed is False and res.p0 is True


# --------------------------------------------------------------------------- #
# Gate E — experiment value (WARN, §3.8): adjust + log, NEVER blocks
#   thin corpus -> value insufficient -> WARN fires + value_adjustment_log entry.
#   exercise corpus -> value sufficient -> WARN passes.
# --------------------------------------------------------------------------- #
def _poolable_viability(corpus_name: str, fixtures_dir: Path, golden_dir: Path) -> dict:
    with gzip.open(fixtures_dir / corpus_name, "rt", encoding="utf-8") as fh:
        works = json.load(fh)["works"]
    picos = json.loads((golden_dir / "research_contract.json").read_text())["synthesis"]["picos"]
    pk = synthesis.poolable_k_by_scale(works, picos, "intervention")
    return {"poolable_k": pk, "max_poolable_k": max(pk.values(), default=0)}


def test_gate_e_thin_corpus_warns_and_logs_but_does_not_block(fixtures_dir, golden_dir):
    viability = _poolable_viability("corpus_mindfulness_thin.json.gz", fixtures_dir, golden_dir)
    assert viability["max_poolable_k"] < paper_gates.POOLABLE_FLOOR   # genuinely thin

    report, res = _run_one({"viability": viability}, "E")
    assert res.severity is Severity.WARN
    assert res.passed is False                       # value-insufficient -> steering fires
    assert res.p0 is False                            # WARN never P0
    assert report.blocked is False                    # WARN NEVER blocks the deliverable
    log = res.evidence["value_adjustment_log"]
    assert log and log["verdict"] == "value-insufficient" and log["action"] == "ADJUST-or-PAUSE"


def test_gate_e_exercise_corpus_value_sufficient(fixtures_dir, golden_dir):
    viability = _poolable_viability("corpus_exercise.json.gz", fixtures_dir, golden_dir)
    assert viability["max_poolable_k"] >= paper_gates.POOLABLE_FLOOR

    report, res = _run_one({"viability": viability}, "E")
    assert res.passed is True and res.p0 is False and report.blocked is False
    assert res.evidence["value_adjustment_log"] is None


def test_gate_e_empty_viability_warns_never_blocks():
    # fail-closed for a WARN gate = signal fires (passed False) but never blocks/P0.
    report, res = _run_one({}, "E")
    assert res.passed is False and res.p0 is False and report.blocked is False


# --------------------------------------------------------------------------- #
# Gate F — logic/coherence (BLOCK): wrap the vendored audit.py 7-scan
# --------------------------------------------------------------------------- #
def test_gate_f_fail_on_planted_contradiction(fixtures_dir):
    draft = (fixtures_dir / "gates" / "contradiction_draft.md").read_text(encoding="utf-8")
    report, res = _run_one({"draft_text": draft, "real_results": GOLDEN_REAL_RESULTS}, "F")
    assert res.passed is False and res.p0 is True and report.blocked is True
    scans = {f.get("scan") for f in res.evidence["fail_items"]}
    assert "contradictions" in scans


def test_gate_f_pass_coherent_draft(fixtures_dir):
    draft = (fixtures_dir / "gates" / "good_draft.md").read_text(encoding="utf-8")
    report, res = _run_one({"draft_text": draft, "real_results": GOLDEN_REAL_RESULTS}, "F")
    assert res.passed is True and res.p0 is False and report.blocked is False
    assert res.evidence["total_fail"] == 0


def test_gate_f_accepts_derived_percentage_from_result_counts():
    draft = (
        "The verified corpus contains 41 references. Machine-readable abstracts were "
        "available for 33/41 records, or 80.5%."
    )
    real_results = {
        "verified_reference_count": 41,
        "abstract_coverage": {
            "machine_readable": 33,
            "total": 41,
            "rate": 0.805,
        },
    }

    report, res = _run_one({"draft_text": draft, "real_results": real_results}, "F")

    assert res.passed is True, res.evidence.get("fail_items")
    assert res.p0 is False
    assert report.blocked is False


def test_gate_f_accepts_numbers_traced_in_claim_evidence_map():
    draft = (
        "The current listed company universe is 1,089 firms. "
        "Mean ESG indicator company coverage is 82.6%."
    )
    real_results = {
        "computed_descriptive_results": {
            "listed_company_universe_n": 1089,
            "mean_esg_indicator_company_coverage": 0.825528,
        }
    }
    claim_evidence = [
        {
            "row": (
                "Current endpoint probing identified 1,089 listed companies. | "
                "real_results listed_company_universe_n = 1089"
            )
        },
        {
            "row": (
                "Mean ESG indicator company coverage of 82.6%. | "
                "real_results mean_esg_indicator_company_coverage = 0.825528"
            )
        },
    ]

    report, res = _run_one(
        {
            "draft_text": draft,
            "real_results": real_results,
            "claim_evidence": claim_evidence,
        },
        "F",
    )

    assert res.passed is True, res.evidence.get("fail_items")
    assert res.p0 is False
    assert report.blocked is False


def test_gate_f_accepts_truncated_grouped_integer_suffix_from_logic_audit():
    draft = (
        "Mandatory ESG disclosure reforms are intended to improve corporate transparency, "
        "but their value depends on whether firms improve the substance of sustainability "
        "reporting rather than merely expanding formal compliance across the current listed "
        "company universe of 1,089 firms."
    )
    real_results = {
        "computed_descriptive_results": {
            "listed_company_universe_n": 1089,
        }
    }

    report, res = _run_one({"draft_text": draft, "real_results": real_results}, "F")

    assert res.passed is True, res.evidence.get("fail_items")
    assert report.blocked is False


def test_gate_f_fail_closed_without_draft():
    _, res = _run_one({"real_results": GOLDEN_REAL_RESULTS}, "F")
    assert res.passed is False and res.p0 is True


# --------------------------------------------------------------------------- #
# paperctl routing — `paperctl gate A|B|C|D|E|F --run-dir RUN` works end-to-end
#   and the legacy phase2/3/8/9/final routing is untouched.
# --------------------------------------------------------------------------- #
def _seed_golden_run(tmp_path: Path, golden_dir: Path, fixtures_dir: Path) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for item in golden_dir.iterdir():
        if item.name in ("_crossref_metadata.json", "_key_map.json"):
            continue
        (shutil.copytree if item.is_dir() else shutil.copy)(item, run_dir / item.name)
    with gzip.open(fixtures_dir / "corpus_exercise.json.gz", "rt", encoding="utf-8") as fh:
        corpus = json.load(fh)
    (run_dir / "_corpus_cache.json").write_text(json.dumps(corpus), encoding="utf-8")
    return run_dir


def test_paperctl_gate_a_to_f_routes_and_blocks(tmp_path, golden_dir, fixtures_dir, capsys):
    import paperctl

    run_dir = _seed_golden_run(tmp_path, golden_dir, fixtures_dir)

    # A/C/D/E pass on the golden run (exit 0); the WARN gate E never blocks.
    for gate in ("A", "C", "D", "E"):
        rc = paperctl.main(["gate", gate, "--run-dir", str(run_dir)])
        out = json.loads(capsys.readouterr().out)
        assert rc == 0, f"gate {gate} unexpectedly blocked: {out['details']}"
        assert out["gate"] == gate and out["passed"] is True


def test_paperctl_gate_a_accepts_v3_doi_audit_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "bib_count": 36,
                "doi_count": 36,
                "doi_real_rate": 1.0,
                "summary": {"doi_real_rate": 1.0},
            }
        ),
        encoding="utf-8",
    )

    rc = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["passed"] is True
    assert out["evidence"] == {"bib_count": 36, "doi_real_rate": 1.0}


def test_paperctl_gate_a_accepts_entries_two_of_three_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "total": 44,
                    "passes_two_of_three": 41,
                    "fails_two_of_three": 3,
                },
                "entries": [
                    {"doi": "10.1000/%s" % idx, "passes_two_of_three": idx < 41}
                    for idx in range(44)
                ],
            }
        ),
        encoding="utf-8",
    )

    rc = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["passed"] is True
    assert out["evidence"] == {"bib_count": 44, "doi_real_rate": 41 / 44}


def test_paperctl_gate_a_prefers_v3_1_canonical_data(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "artifacts" / "data").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps({"bib_count": 35, "doi_real_rate": 0.0}),
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "data" / "canonical.v3_1.json").write_text(
        json.dumps(
            {
                "schema_version": "paperlab.data.v3.1",
                "references": {"count": 40},
                "verification": {"two_source_rate": 1.0},
                "effects": {"poolable_k": 9, "abstract_level_count": 9},
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)
    rc_e = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out_e = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 40, "doi_real_rate": 1.0}
    assert rc_e == 0
    assert out_e["evidence"]["max_poolable_k"] == 9


def test_paperctl_gate_a_prefers_v3_2_canonical_data_over_legacy_inputs(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "artifacts" / "data").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps({"bib_count": 35, "doi_real_rate": 0.0}),
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "data" / "canonical.v3_1.json").write_text(
        json.dumps(
            {
                "schema_version": "paperlab.data.v3.1",
                "references": {"count": 36},
                "verification": {"two_source_rate": 0.8},
                "effects": {"poolable_k": 1, "abstract_level_count": 1},
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "artifacts" / "data" / "canonical.v3_2.json").write_text(
        json.dumps(
            {
                "schema_version": "paperlab.data.v3.2",
                "references": {"count": 41, "two_source_verified": 41},
                "verification": {
                    "two_source_rate": 1.0,
                    "source_artifact": "artifacts/data/doi_verification.v3_2.json",
                },
                "effects": {
                    "poolable_k": 6,
                    "abstract_level_count": 6,
                    "source_artifact": "artifacts/data/effects.v3_2.json",
                },
                "figures": [],
                "human_checkpoint": None,
            }
        ),
        encoding="utf-8",
    )

    rc = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["evidence"] == {"bib_count": 41, "doi_real_rate": 1.0}


def test_paperctl_gate_e_accepts_v3_real_results_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "max_poolable_k": 6,
                "poolable_effects": [{"study": str(i)} for i in range(6)],
            }
        ),
        encoding="utf-8",
    )

    rc = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert out["gate"] == "E"
    assert out["evidence"]["max_poolable_k"] == 6


def test_paperctl_gates_derive_values_from_hermes_summary_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "bib_entries_written": 35,
                    "all_bib_entries_two_source_verified": True,
                },
                "bib_keys": [{"key": str(i)} for i in range(35)],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps({"effects": [{"study": str(i)} for i in range(10)]}),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)
    rc_e = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out_e = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 35, "doi_real_rate": 1.0}
    assert rc_e == 0
    assert out_e["evidence"]["max_poolable_k"] == 10


def test_paperctl_gates_derive_values_from_selected_reference_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "selected_references": 40,
                    "selected_passing_two_source_rule": 40,
                    "selected_with_abstract_field": 40,
                }
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "included_effects": [{"study": "a"}, {"study": "b"}, {"study": "c"}],
                "pooled_smd": {"k": 3},
                "prisma_counts": {"abstract_extractable_effects_in_quantitative_synthesis": 3},
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)
    rc_e = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out_e = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 40, "doi_real_rate": 1.0}
    assert rc_e == 0
    assert out_e["evidence"]["max_poolable_k"] == 3


def test_paperctl_gates_derive_values_from_verification_summary_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "retained_verified_references": 40,
                "verification_summary": {
                    "all_retained_have_abstract": True,
                    "all_retained_verified_by_at_least_two_sources": True,
                },
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "abstract_level_effects": [{"study": "a"}, {"study": "b"}],
                "screening": {"abstract_level_numeric_effects_extracted": 2},
                "synthesis": {"numeric_effect_count": 2},
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)
    rc_e = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out_e = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 40, "doi_real_rate": 1.0}
    assert rc_e == 0
    assert out_e["evidence"]["max_poolable_k"] == 2


def test_paperctl_gates_derive_values_from_audit_summary_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "audit_summary": {
                    "total": 35,
                    "verified_at_least_two_sources": 35,
                    "crossref_pass": 35,
                    "europepmc_pass": 29,
                    "semantic_scholar_pass_or_fallback": 6,
                },
                "records": [
                    {"doi": "10.1000/example.1", "verified": True},
                    {"doi": "10.1000/example.2", "verified": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "abstract_extracted_effects": [
                    {"doi": "10.1000/example.1", "effect": 0.41},
                    {"doi": "10.1000/example.2", "effect": 0.52},
                    {"doi": "10.1000/example.3", "effect": 0.63},
                ],
                "prisma_counts": {"included_in_data_phase": 35},
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)
    rc_e = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out_e = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 35, "doi_real_rate": 1.0}
    assert rc_e == 0
    assert out_e["evidence"]["max_poolable_k"] == 3


def test_paperctl_gates_derive_values_from_included_summary_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "total_candidates_audited": 37,
                    "verified_included_references": 35,
                    "verification_rate_included": 1.0,
                    "abstract_coverage_included": 35,
                },
                "included_keys": ["a", "b", "c"],
                "audit_records": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "abstract_level_outcomes": [
                    {"doi": "10.1000/example.1", "estimate": -0.8},
                    {"doi": "10.1000/example.2", "estimate": -0.6},
                    {"doi": "10.1000/example.3", "estimate": -0.4},
                    {"doi": "10.1000/example.4", "estimate": -0.3},
                ],
                "abstract_numeric_evidence_index": [
                    {"doi": "10.1000/example.1"},
                    {"doi": "10.1000/example.2"},
                ],
                "screening_counts": {"verified_included_references": 35},
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)
    rc_e = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out_e = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 35, "doi_real_rate": 1.0}
    assert rc_e == 0
    assert out_e["evidence"]["max_poolable_k"] == 4


def test_paperctl_gates_derive_values_from_doi_backed_summary_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "schema_version": "paperlab.doi_audit.v3",
                "summary": {
                    "included_doi_backed_references": 35,
                    "crossref_pass": 35,
                    "europepmc_pass": 35,
                    "doi_org_resolves": 23,
                    "two_source_pass_rate": 1.0,
                },
                "items": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "schema_version": "paperlab.real_results.v3",
                "forest_style_data": [
                    {"key": "a", "abstract_direction_score": 1.1},
                    {"key": "b", "abstract_direction_score": 0.9},
                    {"key": "c", "abstract_direction_score": 0.7},
                    {"key": "d", "abstract_direction_score": 0.5},
                    {"key": "e", "abstract_direction_score": 0.3},
                ],
                "doi_verification_summary": {
                    "included_doi_backed_references": 35,
                    "two_source_pass_rate": 1.0,
                },
                "screening": {"included_references": 35},
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)
    rc_e = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out_e = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 35, "doi_real_rate": 1.0}
    assert rc_e == 0
    assert out_e["evidence"]["max_poolable_k"] == 5


def test_paperctl_gate_a_derives_selected_pass_rate_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "selected_count": 35,
                "selected_pass_count": 35,
                "selected_pass_rate": 1.0,
                "records": [
                    {"doi": "10.1000/example.1", "passed_two_of_three": True},
                    {"doi": "10.1000/example.2", "passed_two_of_three": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "abstract_level_effects": [
                    {"doi": "10.1000/example.1", "estimate": 0.4},
                ],
                "reference_pool": {
                    "selected_n": 35,
                    "two_of_three_verification_rate": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 35, "doi_real_rate": 1.0}


def test_paperctl_gates_derive_values_from_included_two_source_schema(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    (run_dir / "real_experiments").mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "included_bib_entries": 35,
                    "included_crossref_verified": 35,
                    "included_semantic_scholar_verified": 35,
                    "included_two_source_verified": 35,
                    "included_two_source_verification_rate": 1.0,
                },
                "included_records": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "abstract_level_effects_extracted": [
                    {"doi": "10.1000/example.1", "estimate": -0.5},
                    {"doi": "10.1000/example.2", "estimate": -0.4},
                ],
                "counts": {
                    "included_references": 35,
                    "standardized_effects_with_ci_extracted": 2,
                },
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)
    rc_e = paperctl.main(["gate", "E", "--run-dir", str(run_dir)])
    out_e = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 35, "doi_real_rate": 1.0}
    assert rc_e == 0
    assert out_e["evidence"]["max_poolable_k"] == 2


def test_paperctl_gate_a_derives_rate_from_v32_included_validation_summary(tmp_path, capsys):
    import paperctl

    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "doi_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "candidates_seen": 69,
                    "included_references": 35,
                    "included_with_two_or_more_validations": 35,
                    "included_with_abstract": 35,
                    "failed_or_excluded_candidates": 34,
                },
                "included": [
                    {"doi": "10.1000/example.%s" % idx, "validation_count": 3}
                    for idx in range(35)
                ],
            }
        ),
        encoding="utf-8",
    )

    rc_a = paperctl.main(["gate", "A", "--run-dir", str(run_dir)])
    out_a = json.loads(capsys.readouterr().out)

    assert rc_a == 0
    assert out_a["evidence"] == {"bib_count": 35, "doi_real_rate": 1.0}


def test_paperctl_gate_b_blocks_on_overclaim_draft(tmp_path, golden_dir, fixtures_dir, capsys):
    import paperctl

    run_dir = _seed_golden_run(tmp_path, golden_dir, fixtures_dir)
    # swap in the overclaim prose as the draft + an EMPTY claim_evidence map so every
    # extracted overclaim is unlisted -> Gate B must hard-block (nonzero exit).
    claims, _ = _claim_evidence_blocks(fixtures_dir)
    (run_dir / "paper_draft_v0.qmd").write_text("\n\n".join(claims), encoding="utf-8")
    (run_dir / "claim_evidence_map.md").write_text("# (empty)\n", encoding="utf-8")

    rc = paperctl.main(["gate", "B", "--run-dir", str(run_dir)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["passed"] is False and out["p0"] is True
    assert out["evidence"]["flagged"], "Gate B reported no flagged claims"


def test_paperctl_legacy_phase_gate_still_works(tmp_path, golden_dir, fixtures_dir, capsys):
    # the A–F routing must NOT break the legacy phase routing (phase9 = content gate).
    import paperctl

    run_dir = _seed_golden_run(tmp_path, golden_dir, fixtures_dir)
    rc = paperctl.main(["gate", "phase9", "--run-dir", str(run_dir)])
    out = json.loads(capsys.readouterr().out)
    assert out["gate"] == "phase9" and rc in (0, 1)   # routes to the legacy backend


def test_gate_d_allows_descriptive_lowercase_placeholder_prose():
    """Live false-kill (v3_bcee9fcada9f, 2026-07-17): the manuscript's honest
    disclosure sentence "9 entries with placeholder audit abstract notes"
    (describing the bib abstract audit) tripped Gate D, because markers were
    matched case-insensitively — the ordinary English word "placeholder" in
    prose was treated as template residue. The healer cannot fix that without
    deleting honest disclosure language: a gate-manufactured unfixable
    finding that burned the job's whole auto-retry budget. Residue tokens are
    ALL-CAPS by convention; descriptive lowercase prose must pass."""
    prose = (
        "The audit reports 26 entries with real metadata abstracts and 9 "
        "entries with placeholder audit abstract notes. " + "Sound academic prose. " * 1200
    )
    report, res = _run_one({"draft_text": prose, "render_ok": True}, "D")
    assert res.passed is True and report.blocked is False


def test_gate_d_still_blocks_allcaps_residue_and_bracketed_forms():
    base = "Sound academic prose. " * 1200
    for residue in ("PLACEHOLDER", "[placeholder]", "[Placeholder]", "TODO:", "TBD"):
        _, res = _run_one({"draft_text": base + " " + residue + " ", "render_ok": True}, "D")
        assert res.passed is False, residue
        assert "placeholder text present" in " ".join(res.evidence["problems"]), residue
