"""Render-quality verify stage — minimal and CONVERGENT by design.

WHY: the self-heal review scores the QMD *source*; a broken figure cross-reference is
invisible there (the `@fig-x` ref AND the `{#fig-x}` label both exist) and only shows in
the COMPILED PDF as `?@fig-x`. So after the content loop, RENDER the PDF and VERIFY that
the figure/table cross-references resolve.

Deliberately NOT a stack of mechanical checks. The real fix is BY-CONSTRUCTION —
`tables.inject_figures` now places each float in the document body, so the defect does
not occur. This stage is just the cheap last check + ONE re-render if a regression
slipped through. A pile of auto-repair scripts never converges ("修改不完"); this owns
exactly ONE render fact (do the figure cross-references resolve) and re-renders at most
once. If it still fails, it reports honestly — it does NOT keep churning the paper.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import number_format
import render_springer
import revision_tasks
import tables

# the single render fact this stage owns: figure/table cross-references must resolve in
# the compiled PDF. (Everything else stays in the terminal delivery_audit, not here.)
_CROSSREF_IDS = {"RQ_CROSSREF"}


def render(run_dir: Path, contract: dict[str, Any]) -> bool:
    """Canonical render: re-inject tables + figures (idempotent, BODY placement) then
    compile. Shared by the pipeline and this stage so both render identically."""
    run_dir = Path(run_dir)
    try:
        tables.inject(run_dir, contract)
        # by-construction: floats land in the body. figspec is lane-aware (the dataset
        # lane's forest/dose/flow vs the meta lane's forest/prisma/method).
        tables.inject_figures(run_dir, figspec=tables.figspec_for(contract))
    except Exception:  # noqa: BLE001 - a missing table/figure must not abort the render
        pass
    return render_springer.render(run_dir, contract)


def broken_crossrefs(run_dir: Path) -> list[dict[str, Any]]:
    """Read the COMPILED PDF and return any unresolved `?@fig-`/`?@tbl-` cross-reference
    issue. Reads the existing PDF — call `render` first."""
    return [i for i in revision_tasks.render_quality_check(Path(run_dir))
            if i.get("id") in _CROSSREF_IDS]


def verify_and_repair(run_dir: Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Render, verify figure cross-references resolve, and re-render ONCE if a
    regression slipped through (with the by-construction fix this should be 0 repairs).
    Honest and convergent: at most one repair pass; if it still fails, report — never
    loop the paper to death."""
    run_dir = Path(run_dir)
    # Presentation precision: round raw-float artifacts in tables + prose to academic display
    # precision. Runs HERE (after number_trace in render_gates) so the academic "<0.001"
    # wording cannot trip the traceability gate. Idempotent.
    number_format.format_qmd(run_dir / "paper_draft_v0.qmd")
    render(run_dir, contract)
    broken = broken_crossrefs(run_dir)
    before = [b.get("id") for b in broken]
    repaired = False
    if broken:                                # regression -> ONE re-inject + re-render
        render(run_dir, contract)
        broken = broken_crossrefs(run_dir)
        repaired = True
    result = {"crossref_ok": not broken, "before": before,
              "remaining": [b.get("id") for b in broken], "repaired": repaired}
    (run_dir / "format_repair.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
