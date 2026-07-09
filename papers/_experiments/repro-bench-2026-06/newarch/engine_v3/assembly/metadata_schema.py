"""paper_meta.json v1 — strict structural metadata contract (hand-rolled validation).

⚠️ Naming: `metadata.json` is TAKEN — in every run dir it is the ~47-record verified
bibliography list (written by run_newarch.py, read by floor_score/job_runner/
delivery_audit). The structural manuscript metadata MUST live in `paper_meta.json`.

The schema is strict on the happy path (unknown keys rejected, no post-hoc
normalization): a model emitting a reasonable-but-non-canonical variant fails
validation with a named finding and is routed back by the repair loop — variants are
refused at the boundary, not absorbed one-by-one after the fact (the patch treadmill
ADR-001 exists to kill). Prose NEVER lives here: an `abstract` key is rejected by
name so the escaping trap cannot re-enter.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .ir import Author, PaperDraftIR, SCHEMA_VERSION, SectionRef

PAPER_META_FILE = "paper_meta.json"
SCHEMA_VERSION_VALUE = "paper_meta.v1"

_SECTION_PATH_RE = re.compile(r"^sections/[A-Za-z0-9_.\-]+\.md$")

REQUIRED_KEYS = (
    "schema_version",
    "layout",
    "title",
    "authors",
    "abstract_ref",
    "bibliography",
    "section_order",
)
OPTIONAL_KEYS = ("keywords", "journal", "csl", "review_record_ref")
ALLOWED_LAYOUTS = ("paper", "slides", "report")


def validate_paper_meta(data: Any) -> list[str]:
    """Return findings (empty = valid). Strict: unknown keys are errors."""
    if not isinstance(data, dict):
        return ["paper_meta.json must be a JSON object, got %s" % type(data).__name__]

    findings: list[str] = []
    allowed = set(REQUIRED_KEYS) | set(OPTIONAL_KEYS)
    for key in sorted(set(data) - allowed):
        if key == "abstract":
            findings.append(
                "paper_meta.json must not carry abstract PROSE: write it to the "
                "abstract_ref section file (sections/00_abstract.md) instead"
            )
        else:
            findings.append("paper_meta.json has unknown key %r" % key)
    for key in REQUIRED_KEYS:
        if key not in data:
            findings.append("paper_meta.json missing required key %r" % key)
    if findings:
        return findings

    if data["schema_version"] != SCHEMA_VERSION_VALUE:
        findings.append(
            "schema_version must be %r, got %r" % (SCHEMA_VERSION_VALUE, data["schema_version"])
        )
    if data["layout"] not in ALLOWED_LAYOUTS:
        findings.append("layout must be one of %s, got %r" % (list(ALLOWED_LAYOUTS), data["layout"]))
    if not isinstance(data["title"], str) or not data["title"].strip():
        findings.append("title must be a non-empty string")

    authors = data["authors"]
    if not isinstance(authors, list) or not authors:
        findings.append("authors must be a non-empty list")
    else:
        for i, author in enumerate(authors):
            if not isinstance(author, dict):
                findings.append("authors[%d] must be an object" % i)
                continue
            if not isinstance(author.get("name"), str) or not author["name"].strip():
                findings.append("authors[%d].name must be a non-empty string" % i)
            for opt in ("email", "affiliation"):
                if opt in author and not isinstance(author[opt], str):
                    findings.append("authors[%d].%s must be a string" % (i, opt))
            for key in sorted(set(author) - {"name", "email", "affiliation"}):
                findings.append("authors[%d] has unknown key %r" % (i, key))

    abstract_ref = data["abstract_ref"]
    if not isinstance(abstract_ref, str) or not _SECTION_PATH_RE.match(abstract_ref):
        findings.append(
            "abstract_ref must be a sections/<name>.md path, got %r" % (abstract_ref,)
        )
    if not isinstance(data["bibliography"], str) or not data["bibliography"].strip():
        findings.append("bibliography must be a non-empty string")

    order = data["section_order"]
    if not isinstance(order, list) or not order:
        findings.append("section_order must be a non-empty list")
    else:
        seen: set[str] = set()
        for i, rel in enumerate(order):
            if not isinstance(rel, str) or not _SECTION_PATH_RE.match(rel):
                findings.append(
                    "section_order[%d] must be a sections/<name>.md path, got %r" % (i, rel)
                )
                continue
            if rel in seen:
                findings.append("section_order[%d] duplicates %r" % (i, rel))
            seen.add(rel)
            if isinstance(abstract_ref, str) and rel == abstract_ref:
                findings.append(
                    "section_order must not contain abstract_ref %r: the assembler "
                    "emits the abstract exactly once itself" % rel
                )

    if "keywords" in data:
        kws = data["keywords"]
        if not isinstance(kws, list) or any(not isinstance(k, str) for k in kws):
            findings.append("keywords must be a list of strings")
    for opt in ("journal", "csl", "review_record_ref"):
        if opt in data and not isinstance(data[opt], str):
            findings.append("%s must be a string" % opt)
    return findings


def load_paper_meta(run_dir: Path | str) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse + validate paper_meta.json. Returns (meta, []) or (None, findings)."""
    path = Path(run_dir) / PAPER_META_FILE
    if not path.is_file():
        return None, ["%s missing" % PAPER_META_FILE]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, ["%s unreadable: %s" % (PAPER_META_FILE, exc)]
    findings = validate_paper_meta(data)
    if findings:
        return None, findings
    return data, []


def ir_from_meta(meta: dict[str, Any], *, abstract: str, sections: list[tuple[str, str]]) -> PaperDraftIR:
    """Build the frozen IR from validated meta + loaded prose."""
    return PaperDraftIR(
        schema_version=SCHEMA_VERSION,
        layout=str(meta["layout"]),
        title=str(meta["title"]).strip(),
        authors=tuple(
            Author(
                name=str(a["name"]).strip(),
                email=str(a.get("email") or "").strip(),
                affiliation=str(a.get("affiliation") or "").strip(),
            )
            for a in meta["authors"]
        ),
        keywords=tuple(str(k).strip() for k in meta.get("keywords") or [] if str(k).strip()),
        bibliography=str(meta["bibliography"]).strip(),
        abstract=abstract,
        abstract_ref=str(meta["abstract_ref"]),
        sections=tuple(SectionRef(rel_path=rel, text=text) for rel, text in sections),
        journal=str(meta.get("journal") or "").strip(),
        csl=str(meta.get("csl") or "").strip(),
    )
