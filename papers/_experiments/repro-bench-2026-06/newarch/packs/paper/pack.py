"""Paper domain pack (#1, proven) — ENGINE_GENERAL_SPEC §2.2.

Wraps the existing newarch deterministic assets (synthesis / meta_analysis /
phase0_calibration / doi / figures / render) behind the framework's DomainPack
seam. The framework calls this through the interface; it never imports it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import synthesis  # newarch deterministic meta-analysis extraction/pooling
from framework import DomainPack, Gate, GateResult, Severity, ViabilityVerdict

# A meta-analysis needs a minimum of compatible (poolable) effects to say anything.
# Tuned in Phase 6 (viability+tier); kept conservative here.
POOLABLE_FLOOR = 5
REFS_FLOOR = 35              # Gate A (DESIGN §3.8)
DOI_REAL_RATE_FLOOR = 0.80   # Gate A


def _work_text(w: dict[str, Any]) -> str:
    return f"{w.get('title') or ''}\n{w.get('abstract') or ''}"


# ── Gate checks (A + C real; B/D/E/F land in Phase 4, fail-closed until then) ──
def _gate_refs(dossier: dict[str, Any]) -> GateResult:
    refs = (dossier.get("evidence") or {}).get("references") or {}
    n = int(refs.get("bib_count") or 0)
    rate = refs.get("doi_real_rate")
    ok = n >= REFS_FLOOR and (rate is None or rate >= DOI_REAL_RATE_FLOOR)
    return GateResult(gate="A", severity=Severity.BLOCK, passed=ok, p0=not ok,
                      details=f"bib_count={n} (floor {REFS_FLOOR}), doi_real_rate={rate}",
                      evidence={"bib_count": n, "doi_real_rate": rate})


def _gate_figures(dossier: dict[str, Any]) -> GateResult:
    figs = (dossier.get("evidence") or {}).get("figures") or []
    ok = len(figs) >= 1
    return GateResult(gate="C", severity=Severity.BLOCK, passed=ok, p0=not ok,
                      details=f"{len(figs)} figure(s) registered",
                      evidence={"n_figures": len(figs)})


def _gate_pending_p4(name: str):
    def _check(_dossier: dict[str, Any]) -> GateResult:
        raise NotImplementedError(f"paper Gate {name} lands in Phase 4")
    return _check


class PaperPack(DomainPack):
    name = "paper"

    def grill_schema(self) -> dict[str, Any]:
        return {
            "intervention": {"prompt": "What intervention/exposure?", "type": "text"},
            "outcome": {"prompt": "What outcome?", "type": "text"},
            "population": {"prompt": "What population?", "type": "text"},
            "synthesis_type": {"prompt": "Synthesis type",
                               "type": "enum",
                               "options": list(synthesis.SYNTHESIS_TYPES)},
        }

    def parse_contract(self, raw: dict[str, Any]) -> dict[str, Any]:
        # The paper contract is already PICOS-shaped from the grill; pass through
        # while guaranteeing the synthesis/picos sub-structure exists.
        c = dict(raw)
        c.setdefault("synthesis", {}).setdefault("picos", {})
        return c

    def data_sources(self) -> list[str]:
        return ["openalex", "europepmc", "crossref"]

    def viability_probe(self, contract: dict[str, Any], sources: dict[str, Any]) -> ViabilityVerdict:
        """Deterministic poolable-k over the (frozen, pre-collected) corpus, via the
        ONE authoritative counter `synthesis.poolable_k_by_scale` (Phase 1) — the
        same count the meta lane + phase0 probe produce, so no path can diverge."""
        corpus = sources.get("corpus") or {}
        works = corpus.get("works") if isinstance(corpus, dict) else corpus
        works = works or []
        syn = (contract.get("synthesis") or {})
        picos = syn.get("picos") or {}
        syn_type = syn.get("type") or "intervention"

        poolable_k = synthesis.poolable_k_by_scale(works, picos, syn_type)
        eligible = sum(1 for w in works
                       if synthesis.screen_picos(_work_text(w), picos)[0])
        max_k = max(poolable_k.values(), default=0)

        viable = max_k >= POOLABLE_FLOOR
        ch = self.contract_hash(contract)
        reason = (f"max poolable-k={max_k} across {len(poolable_k)} scale(s) "
                  f"(floor {POOLABLE_FLOOR}); eligible={eligible}/{len(works)}")
        pivots: list[str] = []
        if not viable:
            pivots = [
                "broaden the outcome family (more synonyms) to recover poolable effects",
                "switch to a scoping/narrative review (no pooling) if effects stay scarce",
            ]
        return ViabilityVerdict(
            viable=viable, reason=reason,
            metric={"max_poolable_k": max_k, "poolable_k": poolable_k, "eligible": eligible,
                    "corpus_size": len(works)},
            candidate_pivots=pivots, contract_hash=ch,
        )

    def section_template(self) -> list[str]:
        return ["Abstract", "Introduction", "Related Work", "Methods", "Results",
                "Discussion", "Limitations", "Conclusion"]

    def gate_registry(self) -> list[Gate]:
        return [
            Gate("A", Severity.BLOCK, _gate_refs, when="after Phase 2"),
            Gate("B", Severity.BLOCK, _gate_pending_p4("B"), when="Phase 7->8"),
            Gate("C", Severity.BLOCK, _gate_figures, when="before Phase 8"),
            Gate("D", Severity.BLOCK, _gate_pending_p4("D"), when="Phase 9"),
            Gate("E", Severity.WARN, _gate_pending_p4("E"), when="Phase 0/1/3 framing"),
            Gate("F", Severity.BLOCK, _gate_pending_p4("F"), when="Phase 8 after writing"),
        ]

    def review_rubric(self) -> dict[str, Any]:
        return {
            "gap_matrix": {"min_gaps": 3, "each_gap_cites_real_ref": True,
                           "differentiation_statement_present": True},
            "claim_evidence": {"every_quantitative_claim_cited": True,
                               "exact_match_vs_real_results": True,
                               "no_unlisted_claim": True},
            "refs": {"min": REFS_FLOOR, "doi_real_rate_floor": DOI_REAL_RATE_FLOOR},
        }

    def render(self, dossier: dict[str, Any], out_dir: Path) -> dict[str, Any]:
        # Deliverable = QMD -> PDF. The full deterministic render is exposed via
        # `paperctl render` (Phase 2); here we return the deliverable descriptor.
        return {"deliverable": "qmd+pdf",
                "qmd": str(Path(out_dir) / "paper_springer.qmd"),
                "pdf": str(Path(out_dir) / "paper_draft_v0.pdf")}
