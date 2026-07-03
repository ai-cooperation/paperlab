from __future__ import annotations

from pathlib import Path

import pytest

from engine_v3.core import GateSeverity, run_gates
from engine_v3.core.contracts import ArtifactRef, Dossier
from engine_v3.packs.paper import PaperPack

pytestmark = pytest.mark.unit


def test_paper_pack_declares_skill_bundle_and_tools():
    pack = PaperPack()
    skills = pack.skill_bundle()
    tools = pack.tool_provider().capabilities()

    assert pack.name == "paper"
    assert "paper-draft" in skills
    assert "literature-synthesis" in skills
    assert "paper-review-skill" in skills
    assert "paper-logic-audit" in skills
    assert "refs.audit" in tools["tools"]
    assert "data.meta_analysis" in tools["tools"]
    assert "render" in tools["tools"]
    assert "dataset-fetch" not in skills
    assert "survey-weighted-analysis" not in skills
    assert "number-trace-writing" not in skills


def test_paper_tool_provider_calls_paperctl_functions_directly(monkeypatch, tmp_path: Path):
    called = []

    def fake_refs_audit(run_dir: Path) -> int:
        called.append(run_dir)
        return 0

    import paperctl

    monkeypatch.setattr(paperctl, "cmd_refs_audit", fake_refs_audit)
    provider = PaperPack().tool_provider()

    result = provider.run("refs.audit", {"run_dir": str(tmp_path)})

    assert result == {"status": "ok", "exit_code": 0, "tool": "refs.audit"}
    assert called == [tmp_path]


def test_paper_tool_provider_rejects_unknown_tool(tmp_path: Path):
    provider = PaperPack().tool_provider()

    with pytest.raises(KeyError, match="unknown paper tool"):
        provider.run("nope", {"run_dir": str(tmp_path)})


def test_paper_pack_gate_registry_runs_through_v3_lifecycle():
    pack = PaperPack()
    dossier = {
        "evidence": {
            "references": {
                "bib_count": 35,
                "doi_real_rate": 0.95,
            }
        }
    }

    report = run_gates(pack, dossier, only={"A"})

    assert report.blocked is False
    assert report.results[0].gate_id == "A"
    assert report.results[0].severity == GateSeverity.BLOCK
    assert report.results[0].passed is True


def test_data_completeness_gate_blocks_missing_declared_outputs():
    pack = PaperPack()

    missing = run_gates(
        pack,
        {"data_completeness": {"status": "blocked", "missing_outputs": ["real_experiments/real_results.json"]}},
        only={"G"},
    )
    complete = run_gates(
        pack,
        {"data_completeness": {"status": "done", "missing_outputs": [], "invalid_outputs": []}},
        only={"G"},
    )

    assert missing.blocked is True
    assert "real_experiments/real_results.json" in missing.results[0].details
    assert complete.blocked is False


def test_review_gate_requires_self_heal_loop_and_log():
    pack = PaperPack()
    thin_review = {
        "review": {"p0_count": 0, "delivery": "pass", "floor_100": 90},
        "review_log_present": False,
    }
    complete_review = {
        "review": {
            "p0_count": 0,
            "delivery": "pass",
            "floor_100": 90,
            "review_method": _review_method_fixture(),
            "review_loop": {
                "status": "passed",
                "rounds": 1,
                "reviewer_model": "codex-class",
                "fixer_model": "big-pickle",
                "independent_reviewer": True,
                "floor_failed": False,
            },
            "dimensions": _review_dimensions_fixture(),
        },
        "review_log_present": True,
        "review_log_text": _DECISION_TRACE_LOG,
    }

    thin = run_gates(pack, thin_review, only={"R"})
    complete = run_gates(pack, complete_review, only={"R"})

    assert thin.blocked is True
    assert "loop_ok=False" in thin.results[0].details
    assert complete.blocked is False


def test_review_gate_rejects_thin_loop_without_expert_dimensions():
    pack = PaperPack()
    dossier = {
        "review": {
            "p0_count": 0,
            "delivery": "pass",
            "floor_100": 90,
            "review_loop": {
                "status": "passed",
                "rounds": 1,
                "reviewer_model": "codex-class",
                "fixer_model": "big-pickle",
                "independent_reviewer": True,
                "floor_failed": False,
            },
        },
        "review_log_present": True,
    }

    report = run_gates(pack, dossier, only={"R"})

    assert report.blocked is True
    assert "dimensions_ok=False" in report.results[0].details


def test_review_gate_accepts_floor_100_score_object():
    pack = PaperPack()
    dossier = {
        "review": {
            "p0_count": 0,
            "delivery": "pass",
            "floor_100": {"status": "passed", "score": 92, "floor_failed": False},
            "review_method": _review_method_fixture(),
            "review_loop": {
                "status": "passed",
                "rounds": 2,
                "reviewer_model": "codex-reviewer",
                "fixer_model": "codex-fixer",
                "independent_reviewer": True,
                "floor_failed": False,
            },
            "dimension_scores": _review_dimensions_fixture(),
        },
        "review_log_present": True,
        "review_log_text": _DECISION_TRACE_LOG,
    }

    report = run_gates(pack, dossier, only={"R"})

    assert report.blocked is False
    assert report.results[0].evidence["floor_100"] == 92



def _review_method_fixture(**overrides):
    method = {
        "schema_version": "paperlab.review_method.v3.2",
        "decision_owner": "hermes",
        "capability_class": "domain_expert_review",
        "selected_skill": "paper-review-skill",
        "selection_reason": "domain expert review before delivery",
        "vip_capability_required": True,
        "vip_capability_available": True,
        "inputs_checked": ["paper_draft_v0.qmd", "references.bib"],
        "reviewed_manuscript_sha256": "f" * 64,
    }
    method.update(overrides)
    return method


_DECISION_TRACE_LOG = (
    "# Quality review log\n\n## Skill Decision Trace\n\n"
    "- selected: paper-review-skill\n"
)


def _review_dimensions_fixture():
    return {
        "academic_rigor": 8.1,
        "novelty_positioning": 8.4,
        "experimental_completeness": 7.8,
        "writing_quality": 8.3,
        "practical_feasibility": 8.0,
        "citation_accuracy": 8.6,
        "format_compliance": 8.5,
    }




def _pass_like_review(**overrides):
    review = {
        "p0_count": 0,
        "delivery": "pass",
        "floor_100": 88,
        "review_method": _review_method_fixture(),
        "review_loop": {
            "status": "passed",
            "rounds": 1,
            "reviewer_model": "codex-reviewer",
            "fixer_model": "big-pickle",
            "independent_reviewer": True,
            "floor_failed": False,
        },
        "dimensions": _review_dimensions_fixture(),
    }
    review.update(overrides)
    return review


def test_review_gate_rejects_deterministic_reviewer_string():
    pack = PaperPack()
    review = _pass_like_review()
    review["review_loop"]["reviewer_model"] = "deterministic bounded final review"
    report = run_gates(
        pack,
        {"review": review, "review_log_present": True, "review_log_text": _DECISION_TRACE_LOG},
        only={"R"},
    )

    assert report.blocked is True
    assert "loop_ok=False" in report.results[0].details


def test_review_gate_requires_review_method_provenance():
    pack = PaperPack()
    review = _pass_like_review()
    del review["review_method"]
    report = run_gates(
        pack,
        {"review": review, "review_log_present": True, "review_log_text": _DECISION_TRACE_LOG},
        only={"R"},
    )

    assert report.blocked is True
    assert "review_method provenance missing" in report.results[0].details


def test_review_gate_requires_skill_decision_trace_in_log():
    pack = PaperPack()
    report = run_gates(
        pack,
        {
            "review": _pass_like_review(),
            "review_log_present": True,
            "review_log_text": "# log\nround 1 passed\n",
        },
        only={"R"},
    )

    assert report.blocked is True
    assert "decision trace" in report.results[0].details


def test_review_gate_rejects_stale_manuscript_hash():
    pack = PaperPack()
    report = run_gates(
        pack,
        {
            "review": _pass_like_review(),
            "review_log_present": True,
            "review_log_text": _DECISION_TRACE_LOG,
            "manuscript_sha256": "0" * 64,
        },
        only={"R"},
    )

    assert report.blocked is True
    assert "stale" in report.results[0].details


def test_review_gate_blocks_when_vip_capability_unavailable():
    pack = PaperPack()
    review = _pass_like_review(
        review_method=_review_method_fixture(vip_capability_available=False)
    )
    report = run_gates(
        pack,
        {"review": review, "review_log_present": True, "review_log_text": _DECISION_TRACE_LOG},
        only={"R"},
    )

    assert report.blocked is True
    assert "vip capability" in report.results[0].details.lower()


def test_delivery_gate_requires_pdf_validation():
    pack = PaperPack()
    dossier = Dossier(job_id="job-1", domain="paper")
    dossier.artifacts["paper_draft_v0.pdf"] = ArtifactRef(path="paper_draft_v0.pdf", sha256="abc")

    missing_validation = run_gates(pack, dossier, only={"Z"})

    assert missing_validation.blocked is True
    assert "validation missing" in missing_validation.results[0].details

    dossier.evidence["delivery_pdf_validation"] = {
        "valid": False,
        "findings": ["PDF was produced by ReportLab fallback, not Quarto/Pandoc"],
    }
    invalid = run_gates(pack, dossier, only={"Z"})

    assert invalid.blocked is True
    assert "ReportLab fallback" in invalid.results[0].details

    dossier.evidence["delivery_pdf_validation"] = {
        "valid": True,
        "producer": "xdvipdfmx",
        "raw_citation_count": 0,
        "unresolved_marker_count": 0,
        "numbered_section_detected": True,
        "findings": [],
    }
    missing_freshness = run_gates(pack, dossier, only={"Z"})

    assert missing_freshness.blocked is True
    assert "review freshness" in missing_freshness.results[0].details

    dossier.evidence["review_freshness"] = {"fresh": False, "findings": ["review verdict is stale: manuscript changed between the Hermes review and format_repair"]}
    stale = run_gates(pack, dossier, only={"Z"})

    assert stale.blocked is True
    assert "stale" in stale.results[0].details

    dossier.evidence["review_freshness"] = {"fresh": True, "findings": []}
    valid = run_gates(pack, dossier, only={"Z"})

    assert valid.blocked is False


def test_paper_pack_pipeline_plan_is_domain_owned():
    plan = PaperPack().pipeline_plan()

    assert [phase.id for phase in plan] == [
        "data",
        "gap",
        "structure",
        "write",
        "claim_evidence",
        "render_gates",
        "review_heal",
        "format_repair",
    ]


def test_paper_pack_viability_probe_delegates_to_real_paper_logic(load_fixture_json):
    pack = PaperPack()

    verdict = pack.viability_probe(
        load_fixture_json("contract_paper.json"),
        {"corpus": load_fixture_json("corpus_exercise.json")},
    )

    assert verdict.viable is True
    assert verdict.metric["max_poolable_k"] == 8
    assert verdict.contract_hash


def test_review_gate_blocks_pass_verdict_while_content_findings_pending():
    """Round 7: a stale-but-valid pass review sailed through preflight while
    the manuscript still carried gate-blocked captions, so Hermes never ran.
    Pending deterministic content findings must fail Gate R so the review
    phase re-runs and the reviewer fixes them."""
    pack = PaperPack()
    report = run_gates(
        pack,
        {
            "review": _pass_like_review(),
            "review_log_present": True,
            "review_log_text": _DECISION_TRACE_LOG,
            "pending_content_findings": [
                "figure caption in paper_draft_v0.qmd claims pooled estimate but real_results has no effects"
            ],
        },
        only={"R"},
    )

    assert report.blocked is True
    assert "pending content finding" in report.results[0].details.lower()


def test_review_gate_passes_when_no_pending_content_findings():
    pack = PaperPack()
    report = run_gates(
        pack,
        {
            "review": _pass_like_review(),
            "review_log_present": True,
            "review_log_text": _DECISION_TRACE_LOG,
            "pending_content_findings": [],
        },
        only={"R"},
    )

    assert report.blocked is False
