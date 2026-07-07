from __future__ import annotations

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_acquire_creates_pid_lock_and_release_removes_it(tmp_path: Path):
    from engine_v3.job_lock import acquire_job_lock, release_job_lock

    lock_dir = tmp_path / "_locks_v3"
    handle = acquire_job_lock(lock_dir, "v3_x")
    assert handle is not None
    lock_file = lock_dir / "v3_x.lock"
    assert lock_file.is_file()

    release_job_lock(handle)
    assert not lock_file.exists()


def test_second_live_acquire_is_refused(tmp_path: Path):
    """The exact bug behind e9e1's polluted state: two revalidate processes
    both claimed the same job. A second acquire while the first is held (and
    its owner is alive) must be refused."""
    from engine_v3.job_lock import acquire_job_lock, release_job_lock

    lock_dir = tmp_path / "_locks_v3"
    first = acquire_job_lock(lock_dir, "v3_x")
    assert first is not None

    second = acquire_job_lock(lock_dir, "v3_x")
    assert second is None  # refused — someone else owns it

    release_job_lock(first)
    third = acquire_job_lock(lock_dir, "v3_x")
    assert third is not None  # free again after release
    release_job_lock(third)


def test_stale_lock_from_dead_pid_is_reclaimable(tmp_path: Path):
    """A lock left by a crashed process (pid no longer alive) must not block
    a legitimate rerun forever."""
    from engine_v3.job_lock import acquire_job_lock, release_job_lock

    lock_dir = tmp_path / "_locks_v3"
    lock_dir.mkdir(parents=True)
    # Write a lock owned by a pid that cannot be alive.
    dead_pid = 2_000_000_000
    (lock_dir / "v3_x.lock").write_text('{"pid": %d}' % dead_pid, encoding="utf-8")

    handle = acquire_job_lock(lock_dir, "v3_x")
    assert handle is not None  # stale lock reclaimed
    release_job_lock(handle)


def test_lock_records_the_owning_pid(tmp_path: Path):
    from engine_v3.job_lock import acquire_job_lock, release_job_lock
    import json

    lock_dir = tmp_path / "_locks_v3"
    handle = acquire_job_lock(lock_dir, "v3_x")
    payload = json.loads((lock_dir / "v3_x.lock").read_text(encoding="utf-8"))
    assert payload["pid"] == os.getpid()
    release_job_lock(handle)


def test_revalidate_skips_a_job_locked_by_another_process(tmp_path: Path):
    """The e9e1 fix at the revalidate layer: if another live process already
    holds the job lock, revalidate must NOT run the job (which would interleave
    phase writes). It skips with an honest 'locked' outcome instead."""
    import revalidate_v3_batch as rv
    from engine_v3.job_lock import acquire_job_lock

    jobs_dir = tmp_path / "jobs"
    (jobs_dir / "v3_locked" / "run").mkdir(parents=True)
    lock_dir = jobs_dir / "_locks_v3"

    # Simulate another live owner by holding the lock (this test process is alive).
    other = acquire_job_lock(lock_dir, "v3_locked")
    assert other is not None

    ran = []

    def fake_run_one(jd, jid):
        ran.append(jid)
        return rv.RunOutcome(job_id=jid, status="done", phases={}, seconds=1.0, has_pdf=True, error=None)

    def fake_validate(jd, job_ids, min_floor=80.0):
        from batch_validate_v3 import JobValidation
        return [JobValidation(
            job_id=job_ids[0], status="unknown", passed=False, phases_done=False,
            gates_done=False, review_ok=False, pdf_ok=False, acceptance_ok=False,
            acceptance_status="locked", floor_100=None, delivery=None, findings=[],
        )]

    rows = rv.revalidate_jobs(jobs_dir, ["v3_locked"], run_one=fake_run_one, validate=fake_validate)

    assert ran == []  # the runner never fired — job was locked by another process
    assert rows[0].run.status == "locked"
    assert "another live process" in (rows[0].run.error or "").lower()
