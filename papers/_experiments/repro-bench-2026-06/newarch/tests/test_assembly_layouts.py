"""ADR-001 §3 domain-generality: layout knowledge lives in the adapter registry,
selected by ir.layout — the assembler holds none. Adding a domain = a new adapter,
zero assembler change (D4 litmus)."""
from __future__ import annotations

import re

import pytest

from engine_v3.assembly import layouts
from engine_v3.assembly.ir import Author, PaperDraftIR, SCHEMA_VERSION


def _ir(layout: str = "paper") -> PaperDraftIR:
    return PaperDraftIR(
        schema_version=SCHEMA_VERSION,
        layout=layout,
        title='A Study of "Things"',
        authors=(Author(name="Cooperation.TW", email="paperlab@cooperation.tw"),),
        keywords=("meta-analysis",),
        bibliography="references.bib",
        abstract="A sufficiently long abstract sentence carrying real content for the layout.",
        abstract_ref="sections/00_abstract.md",
        sections=(),
    )


def test_paper_layout_frontmatter_anchored_at_byte_zero() -> None:
    out = layouts.render_ir(_ir())
    assert out.startswith("---\n")  # ecosystem \A--- invariant
    assert ("---\n\n" + layouts.GENERATED_BANNER) in out


def test_paper_layout_single_abstract_no_frontmatter_key() -> None:
    out = layouts.render_ir(_ir())
    assert len(re.findall(r"(?m)^#{1,3}\s*Abstract\b", out)) == 1
    assert not re.search(r"(?m)^abstract:", out.split("---")[1])


def test_paper_layout_escapes_quotes_in_title() -> None:
    out = layouts.render_ir(_ir())
    assert "'Things'" in out and 'A Study of "Things"' not in out


def test_unknown_layout_raises_not_silent() -> None:
    with pytest.raises(ValueError, match="no layout adapter"):
        layouts.render_ir(_ir(layout="slides"))


def test_registering_a_layout_needs_no_assembler_change() -> None:
    """A new domain registers its adapter in the layout map; the assembler never
    branches on layout, so this is the whole integration point."""
    captured = {}

    def _slides_adapter(ir):
        captured["called"] = ir.layout
        return "SLIDES\n"

    layouts._LAYOUTS["slides"] = _slides_adapter
    try:
        out = layouts.render_ir(_ir(layout="slides"))
        assert out == "SLIDES\n" and captured["called"] == "slides"
    finally:
        del layouts._LAYOUTS["slides"]
