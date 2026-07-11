"""Deterministic assembly boundary (ADR-001 Directory-as-Schema, slice 1)."""
from .assembler import (
    BLOCK_REPORT_FILE,
    GENERATED_BANNER,
    assemble_paper,
    ensure_assembled,
    ir_render_values,
    load_ir,
)
from .ir import AssemblyResult, Author, PaperDraftIR, SectionRef
from .manifest import (
    RENDER_MANIFEST_FILE,
    assembler_fingerprint,
    assembly_source_files,
    freshness_findings,
    is_delivery_stale,
    read_render_manifest,
    render_source_files,
    renderer_fingerprint,
    write_render_manifest,
)
from .metadata_schema import PAPER_META_FILE, load_paper_meta, validate_paper_meta
from .migration import migrate_legacy_run

__all__ = [
    "AssemblyResult",
    "Author",
    "BLOCK_REPORT_FILE",
    "GENERATED_BANNER",
    "PAPER_META_FILE",
    "PaperDraftIR",
    "RENDER_MANIFEST_FILE",
    "SectionRef",
    "assemble_paper",
    "assembler_fingerprint",
    "assembly_source_files",
    "ensure_assembled",
    "freshness_findings",
    "ir_render_values",
    "is_delivery_stale",
    "load_ir",
    "load_paper_meta",
    "migrate_legacy_run",
    "read_render_manifest",
    "render_source_files",
    "renderer_fingerprint",
    "validate_paper_meta",
    "write_render_manifest",
]
