"""Legacy-run migration: reconstruct paper_meta.json + abstract/section sources from
a model-authored paper_draft_v0.qmd, then assemble.

The heading-variant regexes quarantined HERE are the demoted normalizers (ADR-001:
"normalizers demoted to legacy/migration only") — they may never return to the happy
path. Migration is best-effort + idempotent and FAIL-CLOSED: an unrecoverable or
stub abstract refuses to migrate (findings name why) instead of seeding the new
architecture with a placeholder.

Invocation is EXPLICIT (CLI / validation runs), never automatic on resume — an
in-flight legacy job must not be churned by a background migration (§V4 transition).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .assembler import MIN_ABSTRACT_WORDS, MIN_SECTION_WORDS, assemble_paper, _clean_prose
from .ir import AssemblyResult
from .metadata_schema import PAPER_META_FILE, SCHEMA_VERSION_VALUE

DRAFT_FILE = "paper_draft_v0.qmd"
ABSTRACT_REL = "sections/00_abstract.md"

# Every production-seen abstract marker variant (the twice-patched class): heading
# with optional Pandoc attrs, or a bold line. Ends at the next heading or bold-run.
_BODY_ABSTRACT_RE = re.compile(
    r"(?ms)^(?:#{1,3}\s*Abstract\s*(?:\{[^}\n]*\})?|\*\*\s*Abstract\s*\*\*)\s*\n+"
    r"(.*?)(?=\n#{1,3}\s|\n\*\*\s*(?!Keywords)[A-Z]|\Z)"
)
_FM_ABSTRACT_BLOCK_RE = re.compile(r"(?ms)^abstract:\s*\|?\s*\n((?:[ \t]+.*\n?)+)")
_FM_ABSTRACT_INLINE_RE = re.compile(r'(?m)^abstract:\s*"?(.+?)"?\s*$')
_STUB_RE = re.compile(r"\babstract\s+pending\b", re.IGNORECASE)

# Legacy flat section files (WRITE_OUTPUTS order) — reused when substantive.
LEGACY_SECTION_ORDER = (
    "sections/introduction.md",
    "sections/related_work.md",
    "sections/methods.md",
    "sections/results.md",
    "sections/discussion.md",
    "sections/limitations.md",
    "sections/conclusion.md",
)


def _split_frontmatter(text: str) -> tuple[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return "", text
    return match.group(1), text[match.end():]


def _extract_title(front: str) -> str:
    match = re.search(r'(?m)^title:\s*"?(.+?)"?\s*$', front)
    return match.group(1).strip().strip('"') if match else ""


def _extract_abstract(front: str, body: str) -> tuple[str, str]:
    """(abstract, body_without_abstract_section). Body marker first, then the
    frontmatter key — mirrors the retired render-time extractor exactly."""
    body_match = _BODY_ABSTRACT_RE.search(body)
    if body_match:
        text = _clean_prose(body_match.group(1))
        return text, body[: body_match.start()] + body[body_match.end():]
    block = _FM_ABSTRACT_BLOCK_RE.search(front)
    if block:
        return _clean_prose(block.group(1)), body
    inline = _FM_ABSTRACT_INLINE_RE.search(front)
    if inline:
        return _clean_prose(inline.group(1)), body
    return "", body


def _slug(heading: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", heading.strip().lower()).strip("_")
    return slug or "section"


def _strip_trailing_references(body: str) -> str:
    """Drop a trailing References section (heading + any tail): the assembler emits
    its own `## References` and citeproc fills it — leaving the legacy heading inside
    the last section would render a DOUBLE References (caught by the migration test)."""
    return re.sub(r"(?ms)\n#{1,3}\s*References\s*\n(?:(?!^#{1,3}\s).*\n?)*\Z", "\n", body)


def _split_body_sections(body: str) -> list[tuple[str, str]]:
    """Split on TOP-level headings only; nested ##/### stay inside their section's
    body (correct for round-trip: inner headings belong INSIDE the section file)."""
    body = _strip_trailing_references(body)
    matches = list(re.finditer(r"(?m)^(#{1,2})\s+(?!Abstract\b|References\b)([^\n]+)$", body))
    if not matches:
        return []
    top_level = min(len(m.group(1)) for m in matches)
    tops = [m for m in matches if len(m.group(1)) == top_level]
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(tops):
        end = tops[i + 1].start() if i + 1 < len(tops) else len(body)
        chunk = body[m.start():end].strip()
        sections.append(("sections/%02d_%s.md" % (i + 1, _slug(m.group(2))), chunk))
    return sections


def migrate_legacy_run(run_dir: Path | str) -> AssemblyResult:
    """Reconstruct meta + sources from the legacy draft, then assemble. Fail-closed
    on an unrecoverable/stub abstract."""
    run_path = Path(run_dir)
    if (run_path / PAPER_META_FILE).is_file():
        return assemble_paper(run_path)  # already migrated: idempotent
    draft_path = run_path / DRAFT_FILE
    if not draft_path.is_file():
        return AssemblyResult(ok=False, blocked_findings=("no legacy %s to migrate" % DRAFT_FILE,))

    front, body = _split_frontmatter(draft_path.read_text(encoding="utf-8", errors="ignore"))
    abstract, body = _extract_abstract(front, body)
    if not abstract or _STUB_RE.search(abstract):
        return AssemblyResult(
            ok=False,
            blocked_findings=("legacy draft has no recoverable abstract (missing or stub)",),
        )
    if len(abstract.split()) < MIN_ABSTRACT_WORDS:
        return AssemblyResult(
            ok=False,
            blocked_findings=(
                "legacy abstract too thin (%d words < %d)"
                % (len(abstract.split()), MIN_ABSTRACT_WORDS),
            ),
        )

    section_order = _existing_substantive_sections(run_path)
    if not section_order:
        split = _split_body_sections(body)
        if not split:
            return AssemblyResult(
                ok=False, blocked_findings=("legacy draft body has no splittable sections",)
            )
        (run_path / "sections").mkdir(exist_ok=True)
        for rel, text in split:
            (run_path / rel).write_text(text + "\n", encoding="utf-8")
        section_order = [rel for rel, _ in split]

    (run_path / "sections").mkdir(exist_ok=True)
    (run_path / ABSTRACT_REL).write_text(abstract + "\n", encoding="utf-8")
    title = _extract_title(front) or "Untitled Paper"
    meta = {
        "schema_version": SCHEMA_VERSION_VALUE,
        "layout": "paper",
        "title": title,
        "authors": [{"name": "Cooperation.TW", "email": "paperlab@cooperation.tw"}],
        "abstract_ref": ABSTRACT_REL,
        "bibliography": "references.bib",
        "section_order": section_order,
    }
    (run_path / PAPER_META_FILE).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    return assemble_paper(run_path)


def _existing_substantive_sections(run_path: Path) -> list[str]:
    """Reuse the legacy flat section files when ALL are present + substantive —
    they are the model's own prose, better than re-splitting the composed qmd."""
    order: list[str] = []
    for rel in LEGACY_SECTION_ORDER:
        path = run_path / rel
        if not path.is_file():
            return []
        if len(path.read_text(encoding="utf-8", errors="ignore").split()) < MIN_SECTION_WORDS:
            return []
        order.append(rel)
    return order


if __name__ == "__main__":  # explicit migration CLI: python -m engine_v3.assembly.migration <run_dir>
    if len(sys.argv) != 2:
        print("usage: python -m engine_v3.assembly.migration <run_dir>", file=sys.stderr)
        raise SystemExit(2)
    outcome = migrate_legacy_run(Path(sys.argv[1]))
    print(json.dumps({"ok": outcome.ok, "findings": list(outcome.blocked_findings)}, indent=2))
    raise SystemExit(0 if outcome.ok else 1)
