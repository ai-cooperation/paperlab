"""Phase 1* (ENGINE_BUILD_PLAN, codex-resequenced first): the DomainPack seam
(ENGINE_GENERAL_SPEC §2.2) is satisfied by BOTH the paper pack AND a real-ish
insurance pack — proving the contract holds across two real domains before the
deterministic core hardens around paper. The framework imports NO domain.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from framework import DomainPack, Severity, ViabilityVerdict, contract_hash, run_gates
from packs.insurance import InsurancePack
from packs.paper import PaperPack

pytestmark = pytest.mark.unit

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent / "framework"


# ── both packs satisfy the interface ─────────────────────────────────────────
@pytest.mark.parametrize("pack_cls", [PaperPack, InsurancePack])
def test_pack_is_domainpack_with_full_interface(pack_cls):
    pack = pack_cls()                         # instantiable => every abstract implemented
    assert isinstance(pack, DomainPack)
    assert pack.name in {"paper", "insurance"}
    assert isinstance(pack.grill_schema(), dict) and pack.grill_schema()
    assert isinstance(pack.data_sources(), list) and pack.data_sources()
    assert isinstance(pack.section_template(), list) and len(pack.section_template()) >= 5
    assert isinstance(pack.review_rubric(), dict) and pack.review_rubric()
    gates = pack.gate_registry()
    assert gates and all(g.severity in (Severity.BLOCK, Severity.WARN) for g in gates)


# ── the framework never imports a domain (the whole thesis) ──────────────────
def test_framework_imports_no_domain():
    offenders = []
    for py in FRAMEWORK_DIR.glob("*.py"):
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith(("import ", "from ")) and (
                "paper" in s or "insurance" in s or "ifrs" in s
            ):
                offenders.append(f"{py.name}:{i}: {s}")
    assert not offenders, f"framework leaked a domain import: {offenders}"


# ── contract hash = the viability-lock (§5.1) ────────────────────────────────
def test_contract_hash_stable_and_scope_sensitive(load_fixture_json):
    c = load_fixture_json("contract_paper.json")
    h1 = contract_hash(c)
    assert h1 and h1 == contract_hash(dict(c))          # stable across copies
    c2 = json.loads(json.dumps(c))
    c2["synthesis"]["picos"]["require_all"].append(["new-concept"])
    assert contract_hash(c2) != h1                       # PICOS change -> re-probe
    c3 = json.loads(json.dumps(c))
    c3["job_id"] = "different-run"                        # bookkeeping change -> same hash
    assert contract_hash(c3) == h1


# ── paper viability: deterministic poolable-k over the frozen corpus ─────────
def test_paper_viability_over_real_corpus(load_fixture_json):
    contract = load_fixture_json("contract_paper.json")
    corpus = load_fixture_json("corpus_exercise.json")
    v = PaperPack().viability_probe(contract, {"corpus": corpus})
    assert isinstance(v, ViabilityVerdict)
    assert v.viable is True
    assert v.metric["max_poolable_k"] >= 5
    assert v.contract_hash == contract_hash(contract)


# ── insurance viability: target_findings yield over the real KB dir ──────────
def test_insurance_viability_tiers_over_kb(fixtures_dir, load_fixture_json):
    kb = fixtures_dir / "insurance_kb_small"
    oracle = json.loads((kb / "known_findings.json").read_text(encoding="utf-8"))
    contract = load_fixture_json("contract_insurance.json")

    v = InsurancePack().viability_probe(
        contract, {"kb_dir": str(kb), "fresh_window_days": oracle["fresh_window_days"],
                   "as_of": oracle["as_of"]})
    assert v.metric["total_findings"] == oracle["expected"]["total_findings"]   # 5
    assert v.metric["fresh_findings"] == oracle["expected"]["fresh_findings"]   # 4
    assert v.tier_verdicts["shallow"] is True
    assert v.tier_verdicts["standard"] is False and v.tier_verdicts["deep"] is False
    # the contract asks depth=deep -> not viable; pivots offer the viable tier
    assert v.viable is False and v.candidate_pivots


def test_insurance_viability_passed_findings_directly():
    contract = {"synthesis": {"scope": {"depth": "shallow"}}}
    findings = [{"content": f"x{i}", "fresh": True} for i in range(5)]
    v = InsurancePack().viability_probe(contract, {"findings": findings})
    assert v.viable is True and v.tier_verdicts["shallow"] is True


# ── the framework's generic gate lifecycle runs the pack's real gates ────────
def test_insurance_gate_registry_blocks_gatefail_report(fixtures_dir):
    body = (fixtures_dir / "insurance_gatefail" / "report.md").read_text(encoding="utf-8")
    report = run_gates(InsurancePack(), {"report_md": body})
    assert report.blocked is True
    assert {"body_too_thin", "footnote_orphan", "uncited_quantitative"} <= set(report.failed_blocks)
    fired = {r.gate for r in report.results if not r.passed}
    assert "single_source_overreliance" in fired       # WARN fires but does not block


def test_paper_pending_gates_fail_closed_not_silent_pass():
    # B/D/E/F land in Phase 4; until then the lifecycle must fail them CLOSED
    # (a NotImplementedError gate is never a silent pass).
    report = run_gates(PaperPack(), {})
    by_gate = {r.gate: r for r in report.results}
    for g in ("B", "D", "F"):                            # BLOCK gates
        assert by_gate[g].passed is False and "not implemented" in by_gate[g].details
    assert report.blocked is True
