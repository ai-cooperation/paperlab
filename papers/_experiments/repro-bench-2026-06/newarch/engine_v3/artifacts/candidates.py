from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping


CANDIDATE_SCHEMA_VERSION = "paperlab.candidate.v3.1"
CANDIDATE_ROOT = Path("artifacts/candidates")


def freeze_candidate_outputs(
    run_dir: Path,
    *,
    phase: str,
    task_id: str,
    status: str,
    declared_outputs: Iterable[str],
    outputs: Mapping[str, Path],
    changed_files: Iterable[str],
    blockers: Iterable[str],
) -> dict[str, Any]:
    declared = [str(rel) for rel in declared_outputs]
    if not declared and not outputs:
        return {}

    snapshot_dir = CANDIDATE_ROOT / _safe_segment(phase) / _safe_segment(task_id or phase)
    abs_snapshot_dir = run_dir / snapshot_dir
    abs_snapshot_dir.mkdir(parents=True, exist_ok=True)

    output_rows = []
    copied_paths = set()
    for rel in declared:
        src = _safe_output_path(run_dir, rel, outputs.get(rel))
        if src is None or not src.is_file():
            continue
        dst = abs_snapshot_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        candidate_path = _relative_to_run_dir(dst, run_dir)
        output_rows.append(
            {
                "declared_path": rel,
                "candidate_path": candidate_path,
                "sha256": _hash_file(dst),
                "size": dst.stat().st_size,
            }
        )
        copied_paths.add(rel)

    manifest = {
        "schema_version": CANDIDATE_SCHEMA_VERSION,
        "phase": phase,
        "task_id": task_id,
        "status": status,
        "declared_outputs": declared,
        "changed_files": [str(rel) for rel in changed_files],
        "blockers": [str(blocker) for blocker in blockers],
        "outputs": output_rows,
        "missing_outputs": [rel for rel in declared if rel not in copied_paths],
    }
    manifest_path = abs_snapshot_dir / "manifest.v3_1.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "manifest": _relative_to_run_dir(manifest_path, run_dir),
        "outputs": [row["candidate_path"] for row in output_rows],
        "missing_outputs": list(manifest["missing_outputs"]),
    }


def _safe_output_path(run_dir: Path, rel: str, path: Path | None) -> Path | None:
    candidate = path if path is not None else run_dir / rel
    try:
        resolved = Path(candidate).resolve()
        resolved_run_dir = run_dir.resolve()
    except OSError:
        return None
    if resolved != resolved_run_dir and resolved_run_dir not in resolved.parents:
        return None
    return resolved


def _safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    segment = segment.strip("._")
    return segment or "attempt"


def _relative_to_run_dir(path: Path, run_dir: Path) -> str:
    try:
        return str(path.relative_to(run_dir))
    except ValueError:
        return str(path)


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
