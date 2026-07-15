"""V3 user-facing completion notification (contract.notify_email).

Product gap (first external user, 2026-07-15, v3_4dc73d199e17): the submit
flow promises an email, v1/v2 delivered it via job_runner.notify_completion,
but the V3 line never consumed notify_email — the finished paper sat behind
a link nobody sent. These tests pin the replacement loop:

- ensure_user_notified() is idempotent, never raises, and is safe to call
  from every terminal driver (HTTP thread, human-review approve, revalidate).
- Email fires ONLY on deliverable done (all phases done, no pending human
  checkpoint). Blocked/failed jobs never email the user.
- The email is text-only and links the public progress page; the PDF is
  NEVER attached (product decision 2026-07-15).
- Webhook failure leaves no marker so the next terminal driver retries.
"""
from __future__ import annotations

import json
from pathlib import Path

from engine_v3.core import DossierStore
from engine_v3 import notify

ALL_PHASES = (
    "data",
    "gap",
    "structure",
    "write",
    "claim_evidence",
    "render_gates",
    "review_heal",
    "format_repair",
)


class SendSpy:
    def __init__(self, result: dict | None = None, exc: Exception | None = None):
        self.calls: list[dict] = []
        self.result = result or {"status": "sent"}
        self.exc = exc

    def __call__(self, to: str, subject: str, text: str) -> dict:
        self.calls.append({"to": to, "subject": subject, "text": text})
        if self.exc is not None:
            raise self.exc
        return dict(self.result)


def _make_job(
    jobs_dir: Path,
    job_id: str = "v3_notifyjob1",
    *,
    blocked_phase: str | None = None,
    notify_email: str | None = "reader@example.com",
    checkpoint: dict | None = None,
    topic: str = "簽字會計師與財務報表相似性",
) -> Path:
    run_dir = jobs_dir / job_id / "run"
    run_dir.mkdir(parents=True)
    contract: dict = {"topic": topic, "research_question": "Q"}
    if notify_email is not None:
        contract["notify_email"] = notify_email
    (run_dir / "research_contract.input.json").write_text(
        json.dumps(contract, ensure_ascii=False), encoding="utf-8"
    )
    store = DossierStore(run_dir)
    dossier = store.create(job_id=job_id, domain="paper")
    for phase in ALL_PHASES:
        dossier.mark_phase(phase, "blocked" if phase == blocked_phase else "done")
    if checkpoint is not None:
        dossier.evidence["human_checkpoint"] = checkpoint
    store.save(dossier)
    return jobs_dir / job_id


def _marker(job_dir: Path) -> dict | None:
    path = job_dir / notify.MARKER_FILENAME
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def test_deliverable_done_sends_once_then_replays(tmp_path: Path):
    job_dir = _make_job(tmp_path)
    spy = SendSpy()

    first = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=spy)
    second = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=spy)

    assert first["status"] == "sent"
    assert first["to"] == "reader@example.com"
    assert second["status"] == "sent"
    assert second.get("replay") is True
    assert len(spy.calls) == 1
    marker = _marker(job_dir)
    assert marker is not None and marker["status"] == "sent"
    assert marker["to"] == "reader@example.com"


def test_email_links_public_progress_page_and_has_no_attachment(tmp_path: Path):
    _make_job(tmp_path)
    spy = SendSpy()

    notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=spy)

    call = spy.calls[0]
    # Payload is exactly to/subject/text — text-only, nothing attachable.
    assert set(call.keys()) == {"to", "subject", "text"}
    assert "https://paperlab.cooperation.tw/project/?job=v3_notifyjob1" in call["text"]
    assert "附加" in call["text"]  # states the no-attachment policy explicitly
    assert ".pdf" not in call["text"]  # never a direct artifact URL; page owns it
    assert "簽字會計師" in call["subject"]


def test_missing_notify_email_writes_terminal_skip_marker(tmp_path: Path):
    job_dir = _make_job(tmp_path, notify_email=None)
    spy = SendSpy()

    first = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=spy)
    second = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=spy)

    assert first["status"] == "skipped_no_email"
    assert second.get("replay") is True
    assert spy.calls == []
    marker = _marker(job_dir)
    assert marker is not None and marker["status"] == "skipped_no_email"


def test_blocked_job_never_emails_user(tmp_path: Path):
    job_dir = _make_job(tmp_path, blocked_phase="review_heal")
    spy = SendSpy()

    result = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=spy)

    assert result["status"] == "not_ready"
    assert spy.calls == []
    assert _marker(job_dir) is None


def test_pending_human_checkpoint_defers_email_until_approved(tmp_path: Path):
    job_dir = _make_job(
        tmp_path,
        checkpoint={"status": "human_review_required", "phase": "delivery"},
    )
    spy = SendSpy()

    deferred = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=spy)
    assert deferred["status"] == "not_ready"
    assert spy.calls == []

    run_dir = job_dir / "run"
    store = DossierStore(run_dir)
    dossier = store.load()
    dossier.evidence["human_checkpoint"] = {"status": "approved", "phase": "delivery"}
    store.save(dossier)

    approved = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=spy)
    assert approved["status"] == "sent"
    assert len(spy.calls) == 1


def test_webhook_failure_leaves_no_marker_so_next_driver_retries(tmp_path: Path):
    job_dir = _make_job(tmp_path)
    failing = SendSpy(result={"status": "failed", "error": "http_502"})

    failed = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=failing)
    assert failed["status"] == "failed"
    assert _marker(job_dir) is None

    working = SendSpy()
    retried = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=working)
    assert retried["status"] == "sent"
    assert len(working.calls) == 1


def test_ensure_never_raises(tmp_path: Path):
    _make_job(tmp_path)
    exploding = SendSpy(exc=RuntimeError("boom"))

    result = notify.ensure_user_notified(tmp_path, "v3_notifyjob1", send=exploding)

    assert result["status"] in {"failed", "error"}
    assert _marker(tmp_path / "v3_notifyjob1") is None

    missing = notify.ensure_user_notified(tmp_path, "v3_no_such_job", send=SendSpy())
    assert missing["status"] == "not_ready"


def test_phase_status_is_the_single_source_shared_with_routes():
    """Drift guard: routes' terminal-status logic and the notification's
    deliverable check must be the SAME function, not a diverging copy."""
    from engine_v3 import routes

    assert routes._status is notify.phase_status


def test_human_review_approve_endpoint_triggers_notification(tmp_path: Path, monkeypatch):
    from fastapi.testclient import TestClient
    import http_app

    _make_job(
        tmp_path,
        checkpoint={"status": "human_review_required", "phase": "delivery"},
    )
    spy = SendSpy()
    monkeypatch.setattr(notify, "_send_webhook", spy)
    tc = TestClient(
        http_app.create_app(
            jobs_dir=tmp_path,
            start_worker=False,
            engine_v3=True,
            v3_auth_token="secret",
        )
    )

    response = tc.post(
        "/v3/jobs/v3_notifyjob1/human-review",
        json={"decision": "approve", "reviewer": "tester"},
        headers={"Authorization": "Bearer secret"},
    )

    assert response.status_code == 200
    assert len(spy.calls) == 1
    assert spy.calls[0]["to"] == "reader@example.com"
    marker = _marker(tmp_path / "v3_notifyjob1")
    assert marker is not None and marker["status"] == "sent"


def test_revalidate_batch_triggers_notification(tmp_path: Path, monkeypatch):
    from batch_validate_v3 import JobValidation
    from revalidate_v3_batch import RunOutcome, revalidate_jobs

    _make_job(tmp_path)
    spy = SendSpy()
    monkeypatch.setattr(notify, "_send_webhook", spy)

    def fake_run_one(jobs_dir: Path, job_id: str) -> RunOutcome:
        return RunOutcome(
            job_id=job_id,
            status="done",
            phases={phase: "done" for phase in ALL_PHASES},
            seconds=0.1,
            has_pdf=True,
            error=None,
        )

    def fake_validate(jobs_dir, job_ids=None, min_floor=80.0):
        return [
            JobValidation(
                job_id=job_ids[0],
                status="done",
                passed=True,
                phases_done=True,
                gates_done=True,
                review_ok=True,
                pdf_ok=True,
                acceptance_ok=True,
                acceptance_status="pass",
                floor_100=82.0,
                delivery="pass",
                findings=[],
            )
        ]

    revalidate_jobs(tmp_path, ["v3_notifyjob1"], run_one=fake_run_one, validate=fake_validate)

    assert len(spy.calls) == 1
    marker = _marker(tmp_path / "v3_notifyjob1")
    assert marker is not None and marker["status"] == "sent"
