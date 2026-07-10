"""PaperDraftIR v1 — the versioned paper-domain IR the deterministic assembler consumes.

ADR-001 boundary: the model produces content VALUES (abstract prose, section prose,
structural metadata); this IR carries them to a deterministic assembler that owns
artifact SHAPE (frontmatter, headings, layout). Per-domain IRs stay small and
versioned (D4): a slides/report domain adds its own IR + adapter, never a change to
the general assembler contract.
"""
from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = "paperdraft.v1"


@dataclass(frozen=True)
class Author:
    name: str
    email: str = ""
    affiliation: str = ""


@dataclass(frozen=True)
class SectionRef:
    """One ordered body section: where it came from + its prose."""

    rel_path: str
    text: str


@dataclass(frozen=True)
class PaperDraftIR:
    schema_version: str
    layout: str
    title: str
    authors: tuple[Author, ...]
    keywords: tuple[str, ...]
    bibliography: str
    # Abstract prose is loaded FROM the abstract_ref section file — it never lives
    # in paper_meta.json (JSON-escaping trap; ADR-001 RESOLUTION Q1).
    abstract: str
    abstract_ref: str
    sections: tuple[SectionRef, ...]
    journal: str = ""
    csl: str = ""


@dataclass(frozen=True)
class AssemblyResult:
    ok: bool
    written: tuple[str, ...] = ()
    blocked_findings: tuple[str, ...] = ()
    source_sha256: str = ""
    changed: bool = False
