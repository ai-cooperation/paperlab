"""Domain-agnostic orchestration framework (ENGINE_GENERAL_SPEC §2.1).

The framework is written ONCE and never imports a domain. It defines the
DomainPack seam every domain implements, the generic value objects
(ViabilityVerdict, Gate, GateResult), and the gate *lifecycle* (register -> run
-> enforce -> block). Concrete gates / evidence / viability live in the packs.

Invariant (enforced by tests/test_pack_interface.py): zero `import paper_*` /
`import insurance_*` anywhere under framework/.
"""
from .domain_pack import (
    DomainPack,
    Gate,
    GateResult,
    Severity,
    ViabilityVerdict,
    canonicalize_contract,
    contract_hash,
)
from .gate_lifecycle import GateReport, run_gates

__all__ = [
    "DomainPack",
    "Gate",
    "GateResult",
    "Severity",
    "ViabilityVerdict",
    "canonicalize_contract",
    "contract_hash",
    "GateReport",
    "run_gates",
]
