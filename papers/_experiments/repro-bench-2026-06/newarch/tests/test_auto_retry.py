"""#18 auto-retry: bounded, cooldown-aware, never touches human queues."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from auto_retry_v3 import COOLDOWN_S, MAX_ATTEMPTS, record_attempt, select_retry_candidates

pytestmark = pytest.mark.unit


def _job(jobs: Path, jid: str, phases: dict, ledger: dict | None = None) -> None:
    run = jobs / jid / "run"
    run.mkdir(parents=True)
    (run / "dossier.v3.json").write_text(json.dumps({"phases": phases}), encoding="utf-8")
    if ledger is not None:
        (jobs / jid / "auto_retry.json").write_text(json.dumps(ledger), encoding="utf-8")


def test_blocked_job_selected(tmp_path: Path) -> None:
    _job(tmp_path, "v3_aaa", {"write": "done", "review_heal": "blocked"})
    assert select_retry_candidates(tmp_path) == ["v3_aaa"]


def test_all_done_and_human_review_not_selected(tmp_path: Path) -> None:
    _job(tmp_path, "v3_bbb", {"write": "done", "format_repair": "done"})  # incl. awaiting human
    assert select_retry_candidates(tmp_path) == []


def test_budget_exhausted_not_selected(tmp_path: Path) -> None:
    _job(tmp_path, "v3_ccc", {"review_heal": "blocked"}, ledger={"attempts": MAX_ATTEMPTS, "last_attempt_ts": 0})
    assert select_retry_candidates(tmp_path) == []


def test_cooldown_respected(tmp_path: Path) -> None:
    now = time.time()
    _job(tmp_path, "v3_ddd", {"review_heal": "blocked"}, ledger={"attempts": 1, "last_attempt_ts": now - 60})
    assert select_retry_candidates(tmp_path, now=now) == []          # too soon
    assert select_retry_candidates(tmp_path, now=now + COOLDOWN_S) == ["v3_ddd"]  # after cooldown


def test_non_v3_dirs_ignored(tmp_path: Path) -> None:
    _job(tmp_path, "proj_legacy", {"review_heal": "blocked"})
    (tmp_path / "proj_legacy").rename(tmp_path / "proj_old")  # ensure name filter, not just fixture
    assert select_retry_candidates(tmp_path) == []


def test_record_attempt_increments_and_appends(tmp_path: Path) -> None:
    _job(tmp_path, "v3_eee", {"review_heal": "blocked"})
    ledger = record_attempt(tmp_path, "v3_eee", "blocked")
    assert ledger["attempts"] == 1 and ledger["history"][0]["outcome"] == "blocked"
    ledger = record_attempt(tmp_path, "v3_eee", "done")
    assert ledger["attempts"] == 2 and len(ledger["history"]) == 2


def test_stale_blocked_job_not_selected(tmp_path: Path) -> None:
    """28 historical blocked jobs must NOT be auto-retried — only recent activity
    (live customer jobs) qualifies."""
    import os
    from auto_retry_v3 import RECENT_WINDOW_S

    _job(tmp_path, "v3_old", {"review_heal": "blocked"})
    dossier = tmp_path / "v3_old" / "run" / "dossier.v3.json"
    old = time.time() - RECENT_WINDOW_S - 3600
    os.utime(dossier, (old, old))
    assert select_retry_candidates(tmp_path) == []


def test_quota_outage_detected_from_delegation_blockers(tmp_path: Path) -> None:
    """HTTP 429 must not burn the bounded retry budget (2026-07-10: quota ran out
    mid-campaign; each 18s failed attempt said nothing about the job itself)."""
    from auto_retry_v3 import _quota_outage

    run = tmp_path / "v3_q" / "run"
    run.mkdir(parents=True)
    (run / "dossier.v3.json").write_text(json.dumps({
        "phases": {"review_heal": "error"},
        "delegations": [
            {"task_id": "review_heal:brain", "status": "ok", "blockers": []},
            {"task_id": "review_heal:brain", "status": "error",
             "blockers": ["API call failed after 3 retries: HTTP 429: The usage limit has been reached"]},
        ],
    }), encoding="utf-8")
    assert _quota_outage(tmp_path, "v3_q") is True


def test_non_quota_failure_not_treated_as_outage(tmp_path: Path) -> None:
    from auto_retry_v3 import _quota_outage

    run = tmp_path / "v3_r" / "run"
    run.mkdir(parents=True)
    (run / "dossier.v3.json").write_text(json.dumps({
        "phases": {"review_heal": "blocked"},
        "delegations": [
            {"task_id": "review_heal:brain", "status": "blocked",
             "blockers": ["review gate failed: floor below threshold"]},
        ],
    }), encoding="utf-8")
    assert _quota_outage(tmp_path, "v3_r") is False


def test_successful_retry_not_misread_as_outage_from_old_429(tmp_path: Path) -> None:
    """Overnight 2026-07-11: two jobs CONVERGED on retry but the outage scan
    walked past their fresh no-blocker delegations to the pre-retry 429 entry —
    success was reported as 'quota outage', no ledger record, no success TG,
    sweep paused. Only delegations from THIS attempt (since=) may count, and a
    converged status is never an outage."""
    from auto_retry_v3 import _quota_outage

    run = tmp_path / "v3_s" / "run"
    run.mkdir(parents=True)
    (run / "dossier.v3.json").write_text(json.dumps({
        "phases": {"review_heal": "done"},
        "delegations": [
            {"task_id": "review_heal:brain", "status": "error",
             "blockers": ["API call failed after 3 retries: HTTP 429: The usage limit has been reached"]},
            {"task_id": "review_heal:brain", "status": "ok", "blockers": []},
        ],
    }), encoding="utf-8")
    # slice guard: the only 429 predates this attempt
    assert _quota_outage(tmp_path, "v3_s", since=1, status="blocked") is False
    # status guard: converged is never an outage even if a mid-run 429 was logged
    assert _quota_outage(tmp_path, "v3_s", since=0, status="done") is False
    # and the true-outage shape still detects: the 429 IS inside this attempt
    assert _quota_outage(tmp_path, "v3_s", since=0, status="blocked") is True


def test_locked_outcome_consumes_no_budget_and_stays_quiet(tmp_path: Path, monkeypatch) -> None:
    """2026-07-15 live: the timer collided twice with a manual revalidate
    holding the job lock; both lock refusals were recorded as real attempts
    (2/2 budget gone) and each fired a TG alert — the second claimed BUDGET
    EXHAUSTED for a job nothing had actually tried. A lock refusal is an
    infrastructure signal (same family as the HTTP-429 carve-out): it says
    nothing about the JOB, so it must not consume the bounded budget, must
    not alert the admin, and must leave the job selectable next sweep."""
    import sys

    import auto_retry_v3
    import job_runner
    import revalidate_v3_batch

    _job(tmp_path, "v3_lock", {"write": "done", "review_heal": "blocked"})

    class _Run:
        status = "locked"

    class _Row:
        run = _Run()

    monkeypatch.setattr(revalidate_v3_batch, "revalidate_jobs", lambda jobs_dir, ids: [_Row()])
    alerts: list[str] = []
    monkeypatch.setattr(job_runner, "notify_admin", lambda msg: alerts.append(msg))
    monkeypatch.setattr(job_runner, "trigger_status_reconcile", lambda: {"status": "skipped"})
    monkeypatch.setattr(sys, "argv", ["auto_retry_v3.py", "--jobs-dir", str(tmp_path)])

    assert auto_retry_v3.main() == 0

    assert not (tmp_path / "v3_lock" / "auto_retry.json").exists()  # no budget burned
    assert alerts == []  # no false-alarm TG
    assert select_retry_candidates(tmp_path) == ["v3_lock"]  # still selectable
