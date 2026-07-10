"""Single job-lock primitive shared by the HTTP route layer and the CLI
revalidator.

Root cause of e9e1's polluted run state (2026-07-07): revalidate_v3_batch.py
claimed no lock at all, so a probe process and a queue process both ran a
revalidate on the same job and interleaved their phase writes. The HTTP layer
already had a PID-based file lock (_locks_v3); the CLI must acquire the SAME
lock so only one process ever owns a job.

No web dependency here so both importers can use it.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class JobLockHandle:
    fd: int
    path: Path


def _owner_alive(path: Path) -> bool:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not raw:
        # Legacy/empty lock: cannot attribute an owner; treat as reclaimable.
        return False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Non-empty foreign lock: stay conservative and treat as busy.
        return True
    pid = payload.get("pid") if isinstance(payload, dict) else None
    if not isinstance(pid, int) or pid <= 0:
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_job_lock(lock_dir: Path, job_id: str) -> Optional[JobLockHandle]:
    """Atomically claim the lock for job_id. Returns a handle on success, or
    None when another LIVE process already owns it. A stale lock (owner pid
    dead / empty legacy lock) is reclaimed."""
    lock_dir = Path(lock_dir)
    lock_dir.mkdir(parents=True, exist_ok=True)
    path = lock_dir / (job_id + ".lock")
    for _attempt in (0, 1):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _owner_alive(path):
                return None
            # Stale lock — remove and retry the atomic create once.
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        os.write(fd, json.dumps({"pid": os.getpid()}, ensure_ascii=False).encode("utf-8"))
        os.fsync(fd)
        return JobLockHandle(fd=fd, path=path)
    return None


def release_job_lock(handle: Optional[JobLockHandle]) -> None:
    if handle is None:
        return
    try:
        os.close(handle.fd)
    except OSError:
        pass
    try:
        handle.path.unlink()
    except FileNotFoundError:
        pass
