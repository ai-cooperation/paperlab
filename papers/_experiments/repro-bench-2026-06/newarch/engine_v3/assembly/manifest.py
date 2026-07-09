"""Render-freshness manifest: the delivered PDF must provably match its sources.

Two DISTINCT hash sets (ADR-001 §V4-C — conflating them was a reviewed-out bug):

- ASSEMBLY sources (paper_meta.json + abstract + ordered sections): changing any of
  these means the generated qmd must be re-assembled.
- RENDER sources (assembly sources + references.bib + research_contract.json +
  real_experiments/real_results.json + figures/* + code fingerprints): changing any
  of these means the delivered PDF is stale. Enumerated FROM the code — tables.py
  reads real_results + figures, render_springer reads the contract — not from memory
  (§V4-B; the under-enumerated set was reviewed out three times).

Fingerprints are CONTENT-DERIVED (hash of the render/assembly code + CSL +
_extensions), never a manually bumped stamp: an assembler or renderer logic change
with untouched prose sources still invalidates the delivery. Quarto/xelatex binary
drift is explicitly OUT of scope (documented reproducibility limit).

Legacy runs (no paper_meta.json) get an empty finding list / stale=False everywhere:
the freshness gate must never block an in-flight old-contract job (§V4 transition).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from .metadata_schema import PAPER_META_FILE, load_paper_meta

RENDER_MANIFEST_FILE = "render_manifest.json"
MANIFEST_SCHEMA_VERSION = "render_manifest.v1"
DELIVERY_PDF = "paper_draft_v0.pdf"

# newarch root (engine_v3/assembly/manifest.py -> assembly -> engine_v3 -> root)
_ROOT = Path(__file__).resolve().parents[2]

# Render code + assets whose content changes render output (V4-B: content-derived).
_RENDERER_CODE = (
    "render_springer.py",
    "tables.py",
    "number_format.py",
    "format_repair.py",
    "assets/scientometrics.csl",
)


def _digest_files(base: Path, rel_paths: list[str]) -> str:
    """Name-bound content hash: rel path + content per file, missing files bind as
    absent (so add/remove transitions always move the hash)."""
    digest = hashlib.sha256()
    for rel in rel_paths:
        digest.update(rel.encode("utf-8"))
        path = base / rel
        if path.is_file():
            digest.update(b"\x01")
            digest.update(path.read_bytes())
        else:
            digest.update(b"\x00")
    return digest.hexdigest()


def assembly_source_files(run_dir: Path | str) -> list[str] | None:
    """Ordered assembly inputs, or None for a legacy run (no valid paper_meta.json)."""
    meta, _findings = load_paper_meta(run_dir)
    if meta is None:
        return None
    return [PAPER_META_FILE, str(meta["abstract_ref"])] + [str(rel) for rel in meta["section_order"]]


def render_source_files(run_dir: Path | str) -> list[str] | None:
    """Every deterministic render input, or None for a legacy run."""
    assembly = assembly_source_files(run_dir)
    if assembly is None:
        return None
    run_path = Path(run_dir)
    meta, _ = load_paper_meta(run_dir)
    bibliography = str(meta["bibliography"]) if meta else "references.bib"
    files = assembly + [
        bibliography,
        "research_contract.json",
        "real_experiments/real_results.json",
    ]
    figures_dir = run_path / "figures"
    if figures_dir.is_dir():
        files.extend(
            sorted(
                "figures/%s" % p.name
                for p in figures_dir.iterdir()
                if p.is_file() and not p.name.startswith(".")
            )
        )
    return files


def assembly_source_sha256(run_dir: Path | str) -> str | None:
    files = assembly_source_files(run_dir)
    if files is None:
        return None
    return _digest_files(Path(run_dir), files)


def render_source_sha256(run_dir: Path | str) -> str | None:
    files = render_source_files(run_dir)
    if files is None:
        return None
    return _digest_files(Path(run_dir), files)


def assembler_fingerprint() -> str:
    module_dir = Path(__file__).resolve().parent
    rels = sorted(
        str(p.relative_to(module_dir)) for p in module_dir.glob("*.py") if p.is_file()
    )
    return _digest_files(module_dir, rels)


def renderer_fingerprint() -> str:
    rels = list(_RENDERER_CODE)
    ext_dir = _ROOT / "assets" / "_extensions"
    if ext_dir.is_dir():
        rels.extend(
            sorted(
                str(p.relative_to(_ROOT))
                for p in ext_dir.rglob("*")
                if p.is_file() and not p.name.startswith(".")
            )
        )
    return _digest_files(_ROOT, rels)


def write_render_manifest(run_dir: Path | str) -> dict[str, object] | None:
    """Record the source state the delivered PDF was rendered from. Call AFTER the
    render step (so render-time source normalization — sanitize_bib — is already in
    the hashed bytes). Returns the manifest, or None for a legacy run."""
    run_path = Path(run_dir)
    files = render_source_files(run_path)
    if files is None:
        return None
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source_sha256": _digest_files(run_path, files),
        "source_files": files,
        "generated": ["paper_draft_v0.qmd", "paper_springer.qmd"],
        "rendered": DELIVERY_PDF,
        "rendered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "assembler_fingerprint": assembler_fingerprint(),
        "renderer_fingerprint": renderer_fingerprint(),
    }
    (run_path / RENDER_MANIFEST_FILE).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    return manifest


def read_render_manifest(run_dir: Path | str) -> dict[str, object] | None:
    path = Path(run_dir) / RENDER_MANIFEST_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def freshness_findings(run_dir: Path | str) -> list[str]:
    """Empty = delivery provably fresh (or legacy run, where this contract does not
    apply). Non-empty = BLOCK: the delivered PDF cannot be proven to match sources."""
    run_path = Path(run_dir)
    current = render_source_sha256(run_path)
    if current is None:
        return []  # legacy run: freshness contract not applicable (§V4 transition)
    findings: list[str] = []
    manifest = read_render_manifest(run_path)
    if manifest is None:
        return ["%s missing: delivery cannot prove freshness against sources" % RENDER_MANIFEST_FILE]
    recorded = str(manifest.get("source_sha256") or "")
    if recorded != current:
        findings.append(
            "delivery is stale: render sources changed after the last render "
            "(manifest %s… != current %s…); re-assemble and re-render"
            % (recorded[:12], current[:12])
        )
    if str(manifest.get("assembler_fingerprint") or "") != assembler_fingerprint():
        findings.append("delivery is stale: assembler code changed since the last render")
    if str(manifest.get("renderer_fingerprint") or "") != renderer_fingerprint():
        findings.append("delivery is stale: renderer code/assets changed since the last render")
    if not (run_path / DELIVERY_PDF).is_file():
        findings.append("%s missing while a render manifest exists" % DELIVERY_PDF)
    return findings


def is_delivery_stale(run_dir: Path | str) -> bool:
    """Shared staleness predicate for BOTH resume paths (orchestrator skip-guard and
    batch revalidate). Legacy runs are never stale under this contract."""
    return bool(freshness_findings(run_dir))
