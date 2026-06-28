"""The DomainPack seam + generic value objects (ENGINE_GENERAL_SPEC §2.2, §3.5, §5.1).

A pack plugs a domain (paper / insurance / IFRS) into the framework. The framework
calls a pack ONLY through this interface; it never imports the domain. Adding a
domain = write a pack, not touch the framework.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class Severity(str, Enum):
    BLOCK = "BLOCK"   # failing gate fails the deliverable
    WARN = "WARN"     # failing gate annotates only


@dataclass(frozen=True)
class GateResult:
    """The verdict of running one registered gate against a dossier."""
    gate: str
    severity: Severity
    passed: bool
    p0: bool = False
    details: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Gate:
    """A BLOCK/WARN check a pack registers; the framework's lifecycle runs it.

    `check` maps a dossier -> GateResult. Packs supply the gates; the framework
    owns when/how they run and enforces the block. A check that raises is treated
    by the lifecycle as fail-closed (never a silent pass).
    """
    name: str
    severity: Severity
    check: Callable[[dict], GateResult]
    when: str = ""   # human-readable phase hint, e.g. "after Phase 2"


@dataclass(frozen=True)
class ViabilityVerdict:
    """Pack-produced feasibility verdict (§5.1). The framework owns this shape +
    the viability-lock (contract_hash); the pack owns "what makes this domain
    feasible" (paper: poolable-k; insurance: target_findings yield)."""
    viable: bool
    reason: str
    metric: dict[str, Any]
    candidate_pivots: list[str] = field(default_factory=list)
    contract_hash: str = ""
    tier_verdicts: dict[str, bool] = field(default_factory=dict)  # e.g. {"shallow": True, "deep": False}


# ── framework-provided default contract canonicalisation + hash (the lock) ────
_CONTRACT_HASH_FIELDS = (
    "topic", "research_question", "contribution", "data_source", "synthesis", "level",
)


def canonicalize_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Stable subset used for the viability-lock hash. Volatile bookkeeping
    (job_id, timestamps, tier billing) is excluded so the hash tracks the
    *research scope*, not the run instance (§5.1)."""
    return {k: contract.get(k) for k in _CONTRACT_HASH_FIELDS if k in contract}


def contract_hash(contract: dict[str, Any]) -> str:
    canon = canonicalize_contract(contract)
    blob = json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


class DomainPack(ABC):
    """Everything the framework needs to run a domain (ENGINE_GENERAL_SPEC §2.2).

    grill_schema / contract / data_sources / evidence / viability / sections /
    gates / deliverable / rubric. The framework never reads pack-extension dossier
    fields directly — only the pack does (§3.5).
    """

    #: short stable domain id, e.g. "paper" / "insurance" / "ifrs"
    name: str = ""

    # ── scope + contract ─────────────────────────────────────────────────────
    @abstractmethod
    def grill_schema(self) -> dict[str, Any]:
        """Thin, number-free scope questions the front-end asks (§2.3)."""

    @abstractmethod
    def parse_contract(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Canonical contract derived from structured grill answers."""

    def canonicalize(self, contract: dict[str, Any]) -> dict[str, Any]:
        return canonicalize_contract(contract)

    def contract_hash(self, contract: dict[str, Any]) -> str:
        return contract_hash(contract)

    # ── data + evidence + viability ──────────────────────────────────────────
    @abstractmethod
    def data_sources(self) -> list[str]:
        """The domain MCP/tools the agent pulls facts+numbers from (server-side)."""

    @abstractmethod
    def viability_probe(self, contract: dict[str, Any], sources: dict[str, Any]) -> ViabilityVerdict:
        """pack.viability.probe(contract, sources) -> ViabilityVerdict (§5.1)."""

    # ── deliverable shape ────────────────────────────────────────────────────
    @abstractmethod
    def section_template(self) -> list[str]:
        """The deliverable's section outline."""

    @abstractmethod
    def gate_registry(self) -> list[Gate]:
        """The BLOCK/WARN checks this pack registers (run by the framework)."""

    @abstractmethod
    def review_rubric(self) -> dict[str, Any]:
        """Structured-artifact assertions reviewers/tests check."""

    @abstractmethod
    def render(self, dossier: dict[str, Any], out_dir: Path) -> dict[str, Any]:
        """render(dossier) -> the final artifact (returns artifact descriptor)."""
