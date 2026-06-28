"""Submission gate + viability-lock + deterministic contract derivation (P8 / §5.1).

The canonical (a-side) logic. The b-side Worker is a thin client: it calls the a-side
/jobs/viability-probe, stores the lock, and refuses `submit_to_pipeline` without a
hash-matched APPROVED lock. Keeping the rules here (Python, source of truth) means the
TS Worker cannot drift from them.

Invariants (DESIGN §5.1 grill-controllability):
- chat.ai never owns the canonical contract — it is DERIVED deterministically from
  the structured grill answers (not chat prose).
- submit refuses without an approved viability-lock.
- changing title/PICOS after approval changes the contract_hash -> the lock is stale
  -> re-probe required (no silent submit on a changed scope).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .domain_pack import DomainPack
from .domain_pack import contract_hash as _hash


@dataclass(frozen=True)
class ViabilityLock:
    contract_hash: str
    approved: bool
    verdict_viable: bool
    note: str = ""


@dataclass(frozen=True)
class SubmitDecision:
    allowed: bool
    reason: str
    needs_reprobe: bool = False


def derive_contract(pack: DomainPack, grill_answers: dict[str, Any]) -> dict[str, Any]:
    """Deterministically derive the canonical contract from STRUCTURED grill answers
    (never chat prose). The pack owns the field mapping (parse_contract)."""
    contract = pack.parse_contract(dict(grill_answers))
    contract["contract_hash"] = _hash(contract)
    return contract


def lock_for(contract: dict[str, Any], *, approved: bool, verdict_viable: bool,
             note: str = "") -> ViabilityLock:
    return ViabilityLock(contract_hash=_hash(contract), approved=approved,
                         verdict_viable=verdict_viable, note=note)


def submit_gate(contract: dict[str, Any], lock: ViabilityLock | None) -> SubmitDecision:
    """Refuse submit unless an APPROVED viability-lock matches the CURRENT contract's
    hash. A scope change since approval (different title/PICOS) -> hash mismatch ->
    re-probe required."""
    if lock is None:
        return SubmitDecision(False, "no viability-lock: probe + approve before submit")
    if not lock.approved:
        return SubmitDecision(False, "viability-lock not approved")
    current = _hash(contract)
    if current != lock.contract_hash:
        return SubmitDecision(False, "scope changed since approval (hash mismatch): re-probe",
                              needs_reprobe=True)
    if not lock.verdict_viable:
        return SubmitDecision(False, "approved lock records a non-viable verdict")
    return SubmitDecision(True, "approved + hash-matched + viable")
