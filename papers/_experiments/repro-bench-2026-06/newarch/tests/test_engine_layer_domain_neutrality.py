"""Litmus gate for the general-engine intent (V3_2_SPEC.md Decisions D4).

The engine is the general Hermes+Skill research/report engine; paper is only
the FIRST domain proof (insurance / IFRS packs share the framework). General
engine-layer modules must therefore hold ZERO domain-specific artifact names —
domain names live in packs (e.g. engine_v3/packs/paper_artifacts.py).

Ratchet rule: KNOWN_DEBT lists pre-existing violations. It may only SHRINK.
Adding a new entry means you are leaking domain knowledge into the general
layer — move it into the domain pack instead.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ENGINE_ROOT = Path(__file__).resolve().parents[1] / "engine_v3"

# Domain-specific tokens that must not appear in general engine-layer source.
DOMAIN_TOKENS = (
    "paper_draft_v0",
    "paper_springer",
    "quality_review_round1",
    "quality_review_log",
    "references.bib",
    "doi_audit",
    "fig_forest_plot",
    "fig_prisma_flow",
)

# General layer = engine_v3 root modules + core/. packs/, pipelines/,
# artifacts/, runtimes/ are domain or domain-adjacent and may name their own
# artifacts.
GENERAL_LAYER_FILES = sorted(
    list(ENGINE_ROOT.glob("*.py")) + list((ENGINE_ROOT / "core").glob("*.py"))
)

# Pre-existing debt (file -> tokens), recorded 2026-07-02. Only ever remove
# entries; never add.
KNOWN_DEBT: dict[str, set[str]] = {
    "core/orchestrator.py": {"quality_review_round1", "quality_review_log"},
    "routes.py": {"paper_draft_v0", "quality_review_round1"},
}


def _relative(path: Path) -> str:
    return str(path.relative_to(ENGINE_ROOT))


def test_general_engine_layer_holds_no_domain_artifact_names():
    assert GENERAL_LAYER_FILES, "engine_v3 general layer not found"
    violations: list[str] = []
    for path in GENERAL_LAYER_FILES:
        rel = _relative(path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        # strip comments so documentation may mention history without tripping
        code = "\n".join(re.sub(r"#.*$", "", line) for line in text.splitlines())
        allowed = KNOWN_DEBT.get(rel, set())
        for token in DOMAIN_TOKENS:
            if token in code and token not in allowed:
                violations.append("%s contains domain token %r" % (rel, token))
    assert violations == [], (
        "General engine layer leaked domain knowledge (move it into the domain pack):\n"
        + "\n".join(violations)
    )


def test_known_debt_entries_still_exist_so_the_ratchet_stays_honest():
    for rel, tokens in KNOWN_DEBT.items():
        path = ENGINE_ROOT / rel
        assert path.is_file(), "KNOWN_DEBT lists a missing file: %s" % rel
        code = "\n".join(
            re.sub(r"#.*$", "", line)
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        )
        for token in sorted(tokens):
            assert token in code, (
                "KNOWN_DEBT entry %s/%s is stale - the violation was fixed; "
                "remove it from the allowlist to lock in the win" % (rel, token)
            )
