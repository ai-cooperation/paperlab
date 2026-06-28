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
            "review_loop": {
                "status": "passed",
                "rounds": 2,
                "reviewer_model": "codex-reviewer",
                "fixer_model": "codex-fixer",
                "independent_reviewer": "mechanical independent pass",
                "floor_failed": False,
            },
            "dimension_scores": _review_dimensions_fixture(),
        },
        "review_log_present": True,
    }

    report = run_gates(pack, dossier, only={"R"})

    assert report.blocked is False
    assert report.results[0].evidence["floor_100"] == 92


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
