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
