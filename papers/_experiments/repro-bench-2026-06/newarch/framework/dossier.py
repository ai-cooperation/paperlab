"""Dossier — the reasoning-continuity checkpoint (DESIGN §3.3, §3.5).

NOT just artifacts: it stores the decisions, gaps, claim-evidence, gate results,
delegation records and obligations so a FRESH orchestrator session can resume from
it WITHOUT replaying history. The framework reads only the generic CORE; the
pack-specific typed fields live under `pack_ext` and only the pack reads them.

Checkpoints write an atomic manifest with artifact hashes; recovery from partial
worker writes is via re-hashing on resume.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)   # atomic on POSIX


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _now() -> int:
    return int(time.time())


def new_dossier(job_id: str, contract: dict[str, Any], *, mode: str = "paper",
                lane: str = "meta-analysis") -> dict[str, Any]:
    """A generic CORE dossier (DESIGN §3.5). Pack-specific evidence goes in pack_ext."""
    return {
        "schema_version": SCHEMA_VERSION,
        "run": {"job_id": job_id, "mode": mode, "lane": lane,
                "target_journal": contract.get("target_journal"),
                "language": contract.get("output_language", "en")},
        "contract": {k: contract.get(k) for k in
                     ("topic", "research_question", "contribution", "data_source",
                      "synthesis", "level")},
        "status": {"phase": "start", "checkpoint": None, "blocked": False,
                   "blockers": [], "next_action": None},
        "claims": {"research_gaps": [], "contributions": [], "core_claims": [],
                   "claim_evidence": []},
        "evidence": {"references": {}, "real_results": {}, "figures": [], "tables": []},
        "gates": {},
        "delegations": [],
        "revision_loop": {"round": 0, "score": None, "target_score": 80,
                          "remaining_tasks": []},
        "pack_ext": {},      # pack-owned typed extension; framework never reads it
        "_history": [],
    }


@dataclass
class Dossier:
    """File-backed dossier (`dossier.json` in the run dir) + checkpoint manifest."""
    run_dir: Path
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return self.run_dir / "dossier.json"

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "checkpoint_manifest.json"

    # ── lifecycle ────────────────────────────────────────────────────────────
    @classmethod
    def create(cls, run_dir: Path, job_id: str, contract: dict[str, Any],
               **kw: Any) -> "Dossier":
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        d = cls(run_dir=run_dir, data=new_dossier(job_id, contract, **kw))
        d.save()
        return d

    @classmethod
    def load(cls, run_dir: Path) -> "Dossier":
        run_dir = Path(run_dir)
        data = json.loads((run_dir / "dossier.json").read_text(encoding="utf-8"))
        return cls(run_dir=run_dir, data=data)

    def save(self) -> None:
        _atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=2))

    # ── mutation (records reasoning, not just artifacts) ─────────────────────
    def set(self, section: str, value: Any) -> "Dossier":
        self.data[section] = value
        self.data.setdefault("_history", []).append({"set": section, "at": _now()})
        self.save()
        return self

    def update_status(self, **kw: Any) -> "Dossier":
        self.data.setdefault("status", {}).update(kw)
        self.save()
        return self

    def record_delegation(self, rec: dict[str, Any]) -> "Dossier":
        self.data.setdefault("delegations", []).append(rec)
        self.save()
        return self

    def pack_ext_set(self, key: str, value: Any) -> "Dossier":
        """Pack-owned typed extension; the framework never reads these keys."""
        self.data.setdefault("pack_ext", {})[key] = value
        self.save()
        return self

    # ── checkpoint (atomic manifest + artifact hashes; the resume seed) ──────
    def checkpoint(self, name: str, next_action: str,
                   artifacts: list[str] | None = None) -> dict[str, Any]:
        """Mark a checkpoint: record the exact next action + hash the named
        artifacts so a fresh-resume can detect partial/garbled worker writes."""
        arts = {}
        for rel in (artifacts or []):
            p = self.run_dir / rel
            arts[rel] = {"sha256": _sha256(p), "exists": p.exists(),
                         "bytes": p.stat().st_size if p.exists() else 0}
        manifest = {"checkpoint": name, "next_action": next_action,
                    "at": _now(), "artifacts": arts,
                    "phase": self.data.get("status", {}).get("phase")}
        _atomic_write(self.manifest_path,
                      json.dumps(manifest, ensure_ascii=False, indent=2))
        self.update_status(checkpoint=name, next_action=next_action)
        _atomic_write(self.run_dir / "orchestrator_checkpoint.md",
                      f"# Checkpoint: {name}\n\nNext action: {next_action}\n"
                      f"Phase: {manifest['phase']}\nArtifacts: {list(arts)}\n")
        return manifest

    def verify_artifacts(self) -> dict[str, bool]:
        """Re-hash the last checkpoint's artifacts; True == unchanged since checkpoint
        (used on resume to recover from partial worker writes)."""
        if not self.manifest_path.is_file():
            return {}
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        out: dict[str, bool] = {}
        for rel, meta in (manifest.get("artifacts") or {}).items():
            out[rel] = _sha256(self.run_dir / rel) == meta.get("sha256")
        return out

    # ── projection (the webpage-friendly view; P7 status endpoint reads this) ─
    def projection(self) -> dict[str, Any]:
        st = self.data.get("status", {})
        ev = self.data.get("evidence", {})
        return {
            "job_id": self.data.get("run", {}).get("job_id"),
            "phase": st.get("phase"),
            "checkpoint": st.get("checkpoint"),
            "blocked": st.get("blocked", False),
            "blockers": st.get("blockers", []),
            "tier": self.data.get("contract", {}).get("level"),
            "gaps": len(self.data.get("claims", {}).get("research_gaps", [])),
            "refs": (ev.get("references") or {}).get("bib_count"),
            "score": self.data.get("revision_loop", {}).get("score"),
            "round": self.data.get("revision_loop", {}).get("round"),
        }
