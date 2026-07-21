"""A-side consumption of the three peer-review contract fields (grill steps 5 + 7).

The b-side contract carries three OPTIONAL fields that capture the answers to the
three largest reviewer score levers (docs/12 peer-review reverse engineering):

  method.design_rationale     -> methods "design adequacy" statement (Δ−0.93 lever)
  scope_boundary.cannot_claim -> limitations boundary + Gate B hard overclaim ceiling
  differentiation             -> gap/positioning prior-art contrast table (Δ−1.08 lever)

These tests pin BOTH surfaces of consumption:
  1. the static Hermes prompts point the model at the fields;
  2. the deterministic V3.2 fallback generators inject the field content when Hermes
     writes nothing;
  3. Gate B treats cannot_claim as a hard ceiling on overclaiming;
and, critically,
  4. a contract WITHOUT these fields behaves exactly as before (no throw, no block,
     graceful degradation) — the field is content enrichment, never a gate (a64ad5b).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine_v3.core import BrainTask, RuntimeContext
import engine_v3.pipelines.paper as paper_pipeline
from packs.paper import PaperPack
from packs.paper import gates as paper_gates
from framework import run_gates
import paperctl

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _seed_common_artifacts(run_dir: Path, contract: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "research_contract.json").write_text(json.dumps(contract), encoding="utf-8")
    (run_dir / "real_experiments").mkdir(exist_ok=True)
    (run_dir / "real_experiments" / "real_results.json").write_text(
        json.dumps(
            {
                "analysis_type": "deterministic_reference_evidence_map",
                "synthesis": {"numeric_effect_count": 0},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "references.bib").write_text(
        "@article{ref,title={Reference},author={Author, A.},year={2024}}\n", encoding="utf-8"
    )
    (run_dir / "doi_audit.json").write_text(
        '{"records":[{"doi":"10.1000/x","validation_count":2}]}', encoding="utf-8"
    )


def _run_gate_b(dossier: dict):
    report = run_gates(PaperPack(), dossier, only={"B"})
    assert report.results, "gate B not registered"
    return report, report.results[0]


# --------------------------------------------------------------------------- #
# (0) the static Hermes prompts point the model at the three fields
# --------------------------------------------------------------------------- #
def test_gap_prompt_directs_hermes_to_consume_differentiation():
    assert "differentiation" in paper_pipeline.GAP_PHASE_PROMPT


def test_structure_prompt_directs_hermes_to_consume_design_rationale_and_scope():
    prompt = paper_pipeline.STRUCTURE_PHASE_PROMPT
    assert "design_rationale" in prompt
    assert "cannot_claim" in prompt


def test_write_prompt_directs_hermes_to_write_all_three_fields():
    prompt = paper_pipeline.PEER_REVIEW_WRITE_PROMPT
    assert "design_rationale" in prompt
    assert "cannot_claim" in prompt
    assert "differentiation" in prompt
    # and it is actually wired into the write phase prompt
    write_phase = next(p for p in paper_pipeline.full_paper_pipeline() if p.id == "write")
    assert "design_rationale" in write_phase.prompt


# --------------------------------------------------------------------------- #
# (1) design_rationale -> methods architecture (deterministic fallback)
# --------------------------------------------------------------------------- #
def test_structure_fallback_injects_design_rationale_into_methods(tmp_path: Path):
    run_dir = tmp_path / "run"
    rationale = "a 235-country two-way fixed-effects panel with n=5320 country-years licenses the lagged-association claim"
    _seed_common_artifacts(
        run_dir,
        {
            "topic": "DTP3 Coverage and Mortality",
            "research_question": "Estimate lagged associations.",
            "method": {"approach": "twfe panel", "compute": "cpu", "design_rationale": rationale},
        },
    )
    (run_dir / "phase3_positioning.md").write_text("# Research Positioning\n", encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="structure", task_id="structure:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    structure = (run_dir / "phase4_structure.md").read_text(encoding="utf-8")
    methods_section = structure.split("### 3. Methods", 1)[1].split("###", 1)[0]
    assert "Design adequacy" in methods_section
    assert rationale in methods_section


# --------------------------------------------------------------------------- #
# (2a) cannot_claim -> limitations architecture (deterministic fallback)
# --------------------------------------------------------------------------- #
def test_structure_fallback_injects_cannot_claim_into_limitations(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_common_artifacts(
        run_dir,
        {
            "topic": "DTP3 Coverage and Mortality",
            "research_question": "Estimate lagged associations.",
            "method": {"approach": "twfe panel", "compute": "cpu"},
            "scope_boundary": {
                "cannot_claim": [
                    "a causal effect of vaccination on mortality",
                    "generalizability beyond the observed country panel",
                ]
            },
        },
    )
    (run_dir / "phase3_positioning.md").write_text("# Research Positioning\n", encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="structure", task_id="structure:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    structure = (run_dir / "phase4_structure.md").read_text(encoding="utf-8")
    limitations_section = structure.split("### 6. Limitations", 1)[1].split("###", 1)[0]
    assert "Scope Boundary" in limitations_section
    assert "a causal effect of vaccination on mortality" in limitations_section
    assert "generalizability beyond the observed country panel" in limitations_section


# --------------------------------------------------------------------------- #
# (2b) cannot_claim -> Gate B hard overclaim ceiling
# --------------------------------------------------------------------------- #
def test_gate_b_blocks_manuscript_asserting_a_forbidden_claim():
    draft = (
        "## Discussion\n\n"
        "These results establish a causal effect of vaccination on mortality across "
        "the studied countries."
    )
    dossier = {
        "draft_text": draft,
        "claim_evidence": [],
        "real_results": {},
        "scope_boundary": {"cannot_claim": ["a causal effect of vaccination on mortality"]},
    }
    report, res = _run_gate_b(dossier)
    assert res.passed is False and res.p0 is True and report.blocked is True
    flagged_text = " ".join(
        " ".join(f.get("reasons", [])) for f in res.evidence.get("flagged", [])
    ).lower()
    assert "scope_boundary" in flagged_text or "forbids" in flagged_text


def test_gate_b_does_not_flag_honest_disclaimer_of_forbidden_claim():
    # The manuscript RESPECTS the boundary (states it cannot claim it). That is exactly
    # what the contract asked for and must NOT flag.
    draft = (
        "## Limitations\n\n"
        "This study cannot claim a causal effect of vaccination on mortality; the "
        "design supports associations only."
    )
    dossier = {
        "draft_text": draft,
        "claim_evidence": [],
        "real_results": {},
        "scope_boundary": {"cannot_claim": ["a causal effect of vaccination on mortality"]},
    }
    report, res = _run_gate_b(dossier)
    assert res.passed is True and res.p0 is False and report.blocked is False


# --------------------------------------------------------------------------- #
# (3) differentiation -> gap/positioning (deterministic fallback)
# --------------------------------------------------------------------------- #
def test_gap_fallback_injects_differentiation_table(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_common_artifacts(
        run_dir,
        {
            "topic": "DTP3 Coverage and Mortality",
            "research_question": "Estimate lagged associations.",
            "differentiation": [
                {
                    "prior_doi": "10.1016/j.prior2020",
                    "they_did": "used a single-country cross-section",
                    "we_do": "use a 235-country lagged panel",
                },
                {
                    "prior_doi": "10.1016/j.prior2021",
                    "they_did": "measured contemporaneous coverage only",
                    "we_do": "model one-year and two-year lags",
                },
            ],
        },
    )

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="gap", task_id="gap:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    positioning = (run_dir / "phase3_positioning.md").read_text(encoding="utf-8")
    assert "Prior-Art Differentiation" in positioning
    assert "10.1016/j.prior2020" in positioning
    assert "use a 235-country lagged panel" in positioning
    assert "model one-year and two-year lags" in positioning


# --------------------------------------------------------------------------- #
# (4) GRACEFUL DEGRADATION — a contract WITHOUT the three fields behaves as before
# --------------------------------------------------------------------------- #
def test_structure_fallback_without_peer_review_fields_is_unchanged(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_common_artifacts(
        run_dir,
        {"topic": "Plain Topic", "research_question": "Estimate a bounded relationship."},
    )
    (run_dir / "phase3_positioning.md").write_text("# Research Positioning\n", encoding="utf-8")

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="structure", task_id="structure:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    structure = (run_dir / "phase4_structure.md").read_text(encoding="utf-8")
    # the peer-review injections leave NO trace when the fields are absent
    assert "Design adequacy" not in structure
    assert "Scope Boundary" not in structure
    # the phase still produced its normal artifact
    assert "Phase 4 Structure" in structure
    assert "### 3. Methods" in structure


def test_gap_fallback_without_differentiation_is_unchanged(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_common_artifacts(
        run_dir,
        {"topic": "Plain Topic", "research_question": "Estimate a bounded relationship."},
    )

    paper_pipeline._collect_gate_inputs(
        BrainTask(phase="gap", task_id="gap:brain"),
        RuntimeContext(job_id="job-1", run_dir=run_dir),
    )

    positioning = (run_dir / "phase3_positioning.md").read_text(encoding="utf-8")
    assert "Prior-Art Differentiation" not in positioning
    assert "Research Positioning" in positioning


def test_gate_b_without_scope_boundary_behaves_as_before():
    # A clean manuscript with no scope_boundary key -> no cannot_claim flag; the gate
    # only exercises its normal claim<=evidence logic.
    draft = (
        "## Discussion\n\n"
        "The evidence map covers verified references and reports associations only."
    )
    dossier = {"draft_text": draft, "claim_evidence": [], "real_results": {}}
    report, res = _run_gate_b(dossier)
    assert res.passed is True and res.p0 is False and report.blocked is False


def test_gate_b_empty_cannot_claim_list_is_noop():
    draft = "## Discussion\n\nThe study reports bounded associations from verified evidence."
    dossier = {
        "draft_text": draft,
        "claim_evidence": [],
        "real_results": {},
        "scope_boundary": {"cannot_claim": []},
    }
    report, res = _run_gate_b(dossier)
    assert res.passed is True and res.p0 is False and report.blocked is False


# --------------------------------------------------------------------------- #
# dossier surfacing — the CLI exposes scope_boundary only when the contract has it
# --------------------------------------------------------------------------- #
def test_build_dossier_exposes_scope_boundary_when_present(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_common_artifacts(
        run_dir,
        {
            "topic": "T",
            "research_question": "Q",
            "scope_boundary": {"cannot_claim": ["causality", "  ", 5]},
        },
    )
    dossier = paperctl._build_dossier(run_dir)
    assert dossier["scope_boundary"] == {"cannot_claim": ["causality"]}


def test_build_dossier_omits_scope_boundary_when_absent(tmp_path: Path):
    run_dir = tmp_path / "run"
    _seed_common_artifacts(run_dir, {"topic": "T", "research_question": "Q"})
    dossier = paperctl._build_dossier(run_dir)
    assert "scope_boundary" not in dossier


# --------------------------------------------------------------------------- #
# pure helpers — shape tolerance / malformed input never throws
# --------------------------------------------------------------------------- #
def test_contract_readers_tolerate_malformed_shapes():
    assert paper_pipeline._contract_design_rationale({}) == ""
    assert paper_pipeline._contract_design_rationale({"method": "not a dict"}) == ""
    assert paper_pipeline._contract_cannot_claim({"scope_boundary": {"cannot_claim": "x"}}) == []
    assert paper_pipeline._contract_differentiation({"differentiation": "x"}) == []
    # a differentiation row missing we_do is dropped
    rows = paper_pipeline._contract_differentiation(
        {"differentiation": [{"prior_doi": "10.1/x", "they_did": "y"}, {"we_do": "z"}]}
    )
    assert rows == [{"prior_doi": "", "they_did": "", "we_do": "z"}]


def test_gate_b_does_not_flag_boundary_restatement_with_limited_to():
    """Live false-kill (v3_9bb7921f4f2f NILM VIP, 2026-07-21, gate-manufactured
    unfixable finding #6): the manuscript's honest scoping sentence
    'the contribution is limited to a ... calibration-assisted deployment
    framework' was flagged as a P0 overclaim against the boundary entry that
    itself MANDATES the calibration-assisted framing. 'limited to' is the most
    common English scoping verb and must count as a disclaimer."""
    from packs.paper.gates import cannot_claim_violations

    cannot = ["「非侵入」定義限硬體層面；部署階段存在操作介入，本研究明確界定為 calibration-assisted 部署模式"]
    sentence = (
        "Accordingly, the contribution is limited to a DOI-grounded "
        "calibration-assisted deployment framework and simulated-anchor protocol."
    )

    assert cannot_claim_violations(sentence, cannot) == []


def test_gate_b_cjk_entry_term_of_art_alone_is_not_a_violation():
    """A mostly-CJK cannot_claim entry reduces to almost no latin tokens — the
    only survivors are the contract's own term of art (calibration/assisted),
    which every COMPLIANT sentence must also use. CJK runs now join the salient
    tokens, so an English sentence containing just the mandated term no longer
    reaches a 'strong majority' of the entry."""
    from packs.paper.gates import cannot_claim_violations

    cannot = ["「非侵入」定義限硬體層面；部署階段存在操作介入，本研究明確界定為 calibration-assisted 部署模式"]
    sentence = (
        "The calibration-assisted protocol defines the tests to run and records "
        "the current audit and dataset-descriptor support."
    )

    assert cannot_claim_violations(sentence, cannot) == []


def test_gate_b_real_forbidden_assertion_still_blocks():
    """Fail-closed regression: an affirmative assertion of a forbidden claim
    (majority of salient tokens, no disclaimer) must STILL be flagged after
    the disclaimer/token changes."""
    from packs.paper.gates import cannot_claim_violations

    cannot = ["simulated anchor results equal real active-switching calibration performance"]
    violating = (
        "Our simulated anchor results equal real active-switching calibration "
        "performance across all deployments."
    )

    assert cannot_claim_violations(violating, cannot), "real overclaim must stay flagged"
