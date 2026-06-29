from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Mapping

from acceptance_gate_v3 import write_artifact_manifest

from .contracts import ArtifactRef, Dossier


DOSSIER_FILENAME = "dossier.v3.json"


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class DossierStore:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.path = self.run_dir / DOSSIER_FILENAME

    def create(self, job_id: str, domain: str) -> Dossier:
        if not job_id:
            raise ValueError("job_id is required")
        if not domain:
            raise ValueError("domain is required")
        return Dossier(job_id=job_id, domain=domain)

    def load(self) -> Dossier:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return _dossier_from_json(data, self.run_dir)

    def save(self, dossier: Dossier) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        _refresh_artifact_hashes(dossier, self.run_dir)
        payload = _dossier_to_json(dossier, self.run_dir)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(self.path)
        write_artifact_manifest(self.run_dir, payload)

    def exists(self) -> bool:
        return self.path.exists()


def _refresh_artifact_hashes(dossier: Dossier, run_dir: Path) -> None:
    refreshed: Dict[str, ArtifactRef] = {}
    for name, artifact in dossier.artifacts.items():
        path = _artifact_abs_path(artifact.path, run_dir)
        if not path.is_file():
            continue
        refreshed[name] = ArtifactRef(
            path=_artifact_rel_path(path, run_dir),
            sha256=hash_file(path),
        )
    dossier.artifacts = refreshed


def _dossier_to_json(dossier: Dossier, run_dir: Path) -> Mapping[str, Any]:
    return {
        "version": dossier.version,
        "job_id": dossier.job_id,
        "domain": dossier.domain,
        "phases": dict(dossier.phases),
        "artifacts": {
            name: {
                "path": _artifact_rel_path(_artifact_abs_path(ref.path, run_dir), run_dir),
                "sha256": ref.sha256,
            }
            for name, ref in dossier.artifacts.items()
        },
        "evidence": dict(dossier.evidence),
        "gate_reports": list(dossier.gate_reports),
        "delegations": list(dossier.delegations),
    }


def _dossier_from_json(data: Mapping[str, Any], run_dir: Path) -> Dossier:
    artifacts = {
        name: ArtifactRef(path=str(ref["path"]), sha256=str(ref["sha256"]))
        for name, ref in data.get("artifacts", {}).items()
    }
    return Dossier(
        version=int(data.get("version", 3)),
        job_id=str(data["job_id"]),
        domain=str(data["domain"]),
        phases=dict(data.get("phases", {})),
        artifacts=artifacts,
        evidence=dict(data.get("evidence", {})),
        gate_reports=list(data.get("gate_reports", [])),
        delegations=list(data.get("delegations", [])),
    )


def _artifact_abs_path(path: str, run_dir: Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    if p.exists():
        return p.resolve()
    run_parts = run_dir.parts
    path_parts = p.parts
    for index in range(0, len(path_parts)):
        if path_parts[index:index + len(run_parts)] == run_parts:
            return p
    resolved_run = run_dir.resolve()
    resolved_parts = resolved_run.parts
    for index in range(0, len(path_parts)):
        if path_parts[index:index + len(resolved_parts)] == resolved_parts:
            return p
    if len(run_parts) >= 3:
        suffix = run_parts[-3:]
        for index in range(0, len(path_parts)):
            if path_parts[index:index + len(suffix)] == suffix:
                return resolved_run / Path(*path_parts[index + len(suffix):])
    return run_dir / p


def _artifact_rel_path(path: Path, run_dir: Path) -> str:
    try:
        return str(path.relative_to(run_dir))
    except ValueError:
        return str(path)
