from __future__ import annotations

from pathlib import Path

import pytest

from engine_v3.core import GateSeverity, run_gates
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
