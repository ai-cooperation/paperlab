"""Bounded auto-retry for repairable blocked V3 jobs (#18).

沉默失敗=設計缺陷: a job that ends blocked used to sit until a human noticed and
re-drove it by hand (this happened three times in one day during the fresh-E2E
campaign). This scanner re-drives blocked jobs through the full revalidate loop —
BOUNDED (max attempts per job, cooldown between attempts), lock-aware, and every
outcome is reported to the Telegram admin channel so nothing converges or fails
silently.

Deliberately NOT retried:
- jobs with all phases done (incl. human_review_required — that is a human's queue)
- jobs another live process owns (job lock)
- jobs that exhausted the retry budget (terminal: a human decision is required —
  the ledger + TG alert make that explicit instead of silent)

Run via systemd user timer (paper-auto-retry.timer) or manually:
    .venv/bin/python auto_retry_v3.py [--jobs-dir jobs] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

MAX_ATTEMPTS = 2
COOLDOWN_S = 15 * 60
# Only jobs with RECENT activity are auto-retried: a live customer job, not
# archaeology. First dry-run found 28 historical blocked v3 jobs — retrying them
# all would burn 28x2 full Hermes runs on abandoned iterations (validate-before-
# scale caught this before the first timer fire).
RECENT_WINDOW_S = 48 * 3600
LEDGER_NAME = "auto_retry.json"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def select_retry_candidates(jobs_dir: Path, now: float | None = None) -> list[str]:
    """Pure selection: blocked v3 jobs within budget + cooldown. Lock state is
    checked at execution time (between selection and run it can change)."""
    now = time.time() if now is None else now
    candidates: list[str] = []
    for job_dir in sorted(jobs_dir.glob("v3_*")):
        run_dir = job_dir / "run"
        dossier_path = run_dir / "dossier.v3.json"
        dossier = _read_json(dossier_path)
        if not isinstance(dossier, dict):
            continue
        try:
            if now - dossier_path.stat().st_mtime > RECENT_WINDOW_S:
                continue  # historical job: never auto-retry archaeology
        except OSError:
            continue
        phases = dossier.get("phases") or {}
        if not phases or not any(v in ("blocked", "error") for v in phases.values()):
            continue  # all-done (incl. awaiting human review) or not started
        ledger = _read_json(job_dir / LEDGER_NAME) or {}
        attempts = int(ledger.get("attempts") or 0)
        if attempts >= MAX_ATTEMPTS:
            continue
        last = float(ledger.get("last_attempt_ts") or 0)
        if now - last < COOLDOWN_S:
            continue
        candidates.append(job_dir.name)
    return candidates


def record_attempt(jobs_dir: Path, job_id: str, outcome: str) -> dict:
    path = jobs_dir / job_id / LEDGER_NAME
    ledger = _read_json(path) or {"attempts": 0, "history": []}
    ledger["attempts"] = int(ledger.get("attempts") or 0) + 1
    ledger["last_attempt_ts"] = time.time()
    ledger.setdefault("history", []).append(
        {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "outcome": outcome}
    )
    path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    return ledger


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded auto-retry for blocked V3 jobs.")
    parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    candidates = select_retry_candidates(args.jobs_dir)
    if not candidates:
        print("AUTO_RETRY no candidates", flush=True)
        return 0
    if args.dry_run:
        print("AUTO_RETRY dry-run candidates: %s" % ", ".join(candidates), flush=True)
        return 0

    import job_runner
    from revalidate_v3_batch import revalidate_jobs

    for job_id in candidates:
        print("AUTO_RETRY start %s" % job_id, flush=True)
        try:
            rows = revalidate_jobs(args.jobs_dir, [job_id])
            status = rows[0].run.status if rows else "no-result"
        except Exception as exc:  # noqa: BLE001 - one job must not kill the sweep
            status = "exception: %s" % str(exc)[:120]
        if _quota_outage(args.jobs_dir, job_id):
            # 2026-07-10: the model quota ran out mid-campaign (HTTP 429) and the
            # uplift attempts failed in ~18s each. A 429 says nothing about the JOB —
            # do NOT burn its bounded retry budget on an infrastructure outage, and
            # stop the sweep (every subsequent job would 429 too). The timer will
            # simply try again next window; once quota returns, retries resume with
            # full budgets.
            job_runner.notify_admin(
                "Auto-retry paused: model quota exhausted (HTTP 429) while retrying %s. "
                "No retry budgets consumed; will retry automatically when quota returns." % job_id
            )
            print("AUTO_RETRY quota-outage, sweep paused", flush=True)
            return 0
        ledger = record_attempt(args.jobs_dir, job_id, status)
        exhausted = ledger["attempts"] >= MAX_ATTEMPTS and status not in ("done", "human_review_required")
        job_runner.notify_admin(
            "Auto-retry %s -> %s (attempt %d/%d)%s"
            % (
                job_id,
                status,
                ledger["attempts"],
                MAX_ATTEMPTS,
                "\nBUDGET EXHAUSTED: needs a human decision" if exhausted else "",
            )
        )
        print("AUTO_RETRY done %s -> %s" % (job_id, status), flush=True)
    return 0


def _quota_outage(jobs_dir: Path, job_id: str) -> bool:
    """Did this attempt die on a model-quota error (HTTP 429 / usage limit)? Read
    the run's own delegation blockers — the producing system's ground truth."""
    dossier = _read_json(jobs_dir / job_id / "run" / "dossier.v3.json") or {}
    for delegation in reversed(dossier.get("delegations") or []):
        for blocker in delegation.get("blockers") or []:
            text = str(blocker).lower()
            if "429" in text or "usage limit" in text or "rate limit" in text:
                return True
        if delegation.get("blockers"):
            return False  # most recent failed delegation had non-quota blockers
    return False


if __name__ == "__main__":
    raise SystemExit(main())
