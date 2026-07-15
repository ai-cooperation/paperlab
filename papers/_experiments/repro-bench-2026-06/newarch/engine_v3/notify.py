"""User-facing completion notification for V3 jobs (contract.notify_email).

The submission flow promises the requester an email when their paper is
ready. V1/V2 delivered on that in job_runner.notify_completion; the V3 line
never consumed notify_email at all — the first external user (2026-07-15,
v3_4dc73d199e17) got a finished paper nobody told them about.

This closes the gap as a loop, not a patch: ensure_user_notified() is an
idempotent, never-raising primitive that EVERY terminal driver calls
unconditionally — the HTTP job thread, the human-review approve endpoint,
and the CLI/timer revalidate batch. The function itself decides:

- deliverable?   all phases done AND no pending human checkpoint. Blocked or
  failed jobs never email the user (admin TG paths already cover those).
- owed?          contract.notify_email present; a missing email writes a
  terminal skip marker so the question is settled once.
- already sent?  jobs/<job_id>/user_notification.json marker (idempotency).

The email is text-only and NEVER attaches the PDF: it links the public
progress page (no login required) where the PDF can be downloaded — product
decision 2026-07-15. Webhook failure writes NO marker, so the next terminal
driver retries; the admin gets a TG fallback so a promised email is never
dropped silently (same contract as job_runner.notify_completion).
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from engine_v3.core import DossierStore

MARKER_FILENAME = "user_notification.json"
PROGRESS_URL_TEMPLATE = "https://paperlab.cooperation.tw/project/?job=%s"
_TERMINAL_MARKER_STATUSES = {"sent", "skipped_no_email"}

Send = Callable[[str, str, str], dict[str, Any]]


def phase_status(phases: dict[str, str]) -> str:
    """Single source for the phase-map -> job-status projection.

    routes._status aliases this function (drift-guarded by test); the
    notification's deliverable check and the status endpoint must never
    disagree about what "done" means.
    """
    if not phases:
        return "accepted"
    if any(status == "error" for status in phases.values()):
        return "failed"
    if any(status == "blocked" for status in phases.values()):
        return "blocked"
    if phases.get("format_repair") == "done":
        return "done"
    if any(phase in phases for phase in ("gap", "structure", "write", "claim_evidence", "review_heal")):
        return "running"
    if phases.get("render_gates") == "done":
        return "done"
    return "running"


def ensure_user_notified(jobs_dir: Path, job_id: str, *, send: Send | None = None) -> dict[str, Any]:
    """Idempotent, never-raising. Safe to call from any driver at any time."""
    try:
        return _ensure(Path(jobs_dir), job_id, send=send or _send_default)
    except Exception as exc:  # noqa: BLE001 - notification must never break the job
        return {"status": "error", "job_id": job_id, "error": str(exc)[:300]}


def _ensure(jobs_dir: Path, job_id: str, *, send: Send) -> dict[str, Any]:
    job_dir = jobs_dir / job_id
    marker_path = job_dir / MARKER_FILENAME
    marker = _read_json(marker_path)
    if isinstance(marker, dict) and marker.get("status") in _TERMINAL_MARKER_STATUSES:
        return {**marker, "replay": True}

    run_dir = job_dir / "run"
    store = DossierStore(run_dir)
    if not store.exists():
        return {"status": "not_ready", "job_id": job_id, "reason": "no dossier"}
    dossier = store.load()
    if phase_status(dossier.phases) != "done":
        return {"status": "not_ready", "job_id": job_id, "reason": "job is not deliverable done"}
    checkpoint = dossier.evidence.get("human_checkpoint")
    if isinstance(checkpoint, dict) and checkpoint.get("status") == "human_review_required":
        return {"status": "not_ready", "job_id": job_id, "reason": "pending human review"}

    contract = _load_contract(run_dir)
    email = str(contract.get("notify_email") or "").strip()
    if not email:
        skip = {
            "status": "skipped_no_email",
            "job_id": job_id,
            "at": _now_iso(),
        }
        _write_json(marker_path, skip)
        return skip

    subject, text = _compose_email(job_id, str(contract.get("topic") or job_id))
    try:
        result = send(email, subject, text)
    except Exception as exc:  # noqa: BLE001 - a raising sender counts as failed, retry later
        result = {"status": "failed", "error": str(exc)[:300]}
    if isinstance(result, dict) and result.get("status") == "sent":
        sent = {
            "status": "sent",
            "job_id": job_id,
            "to": email,
            "subject": subject,
            "at": _now_iso(),
            "via": str(result.get("via") or "notify_webhook"),
        }
        _write_json(marker_path, sent)
        return sent
    # No marker: the next terminal driver retries. Tell the admin so the
    # promised email is never dropped silently.
    detail = str((result or {}).get("error") or (result or {}).get("detail") or "unknown")[:200]
    _notify_admin_best_effort(
        "Paper Lab v3 user notification FAILED for %s (to %s): %s" % (job_id, email, detail)
    )
    return {"status": "failed", "job_id": job_id, "to": email, "error": detail}


def _compose_email(job_id: str, topic: str) -> tuple[str, str]:
    progress_url = PROGRESS_URL_TEMPLATE % job_id
    subject = "Paper Lab 論文完成通知：%s" % topic[:60]
    text = (
        "您好：\n"
        "\n"
        "您在 Paper Lab 提交的研究題目已完成論文草稿產出。\n"
        "\n"
        "題目：%s\n"
        "工作編號：%s\n"
        "\n"
        "請由以下連結查看處理進度與結果，並在頁面中下載論文 PDF 報告：\n"
        "%s\n"
        "\n"
        "本信件不附加任何檔案；PDF 請一律由上方頁面下載。\n"
        "若連結無法點選，請將網址完整複製到瀏覽器開啟。\n"
        "\n"
        "Paper Lab\n"
        "https://paperlab.cooperation.tw\n"
    ) % (topic, job_id, progress_url)
    return subject, text


def _send_default(to: str, subject: str, text: str) -> dict[str, Any]:
    """Production sender. GAS relay first (free path — Cloudflare Email
    Sending is Workers-Paid-only, decision 2026-07-15), Cloudflare worker as
    the fallback shape when GAS is not configured."""
    if os.environ.get("NOTIFY_GAS_URL", "").strip():
        return _send_gas(to, subject, text)
    return _send_webhook(to, subject, text)


def _send_gas(to: str, subject: str, text: str) -> dict[str, Any]:
    """POST to the notify_gas Apps Script relay (deployed under
    aicooperation.tw@gmail.com; see notify_gas/Code.js). GAS cannot read
    request headers, so the token rides INSIDE the JSON body, and GAS answers
    HTTP 200 even for failures — the JSON body is the verdict."""
    url = os.environ.get("NOTIFY_GAS_URL", "").strip()
    token = os.environ.get("NOTIFY_GAS_TOKEN", "").strip()
    if not url or not token:
        return {"status": "failed", "error": "NOTIFY_GAS_URL/TOKEN not configured"}
    try:
        status_code, body = _post_json(
            url,
            {"token": token, "to": to, "subject": subject, "text": text},
            {"Content-Type": "application/json"},
            30,
        )
    except Exception as exc:  # noqa: BLE001 - network failure is a retryable outcome
        return {"status": "failed", "error": str(exc)[:300]}
    parsed = _parse_json(body)
    if status_code == 200 and isinstance(parsed, dict) and parsed.get("status") == "sent":
        return {"status": "sent", "via": "notify_gas", "detail": body[:300]}
    error = ""
    if isinstance(parsed, dict):
        error = str(parsed.get("error") or "")
    return {"status": "failed", "error": ("http_%s %s" % (status_code, error or body[:200])).strip()}


def _send_webhook(to: str, subject: str, text: str) -> dict[str, Any]:
    """POST to the paper-notify Cloudflare worker (same env contract as
    job_runner._notify_via_webhook; kept separate so engine_v3 stays free of
    the legacy v1/v2 runner module)."""
    url = os.environ.get("NOTIFY_WEBHOOK_URL", "").strip()
    token = os.environ.get("NOTIFY_WEBHOOK_TOKEN", "").strip()
    if not url or not token:
        return {"status": "failed", "error": "NOTIFY_WEBHOOK_URL/TOKEN not configured"}
    try:
        status_code, body = _post_json(
            url,
            {"to": to, "subject": subject, "text": text},
            {"Content-Type": "application/json", "Authorization": "Bearer %s" % token},
            20,
        )
    except Exception as exc:  # noqa: BLE001 - network failure is a retryable outcome
        return {"status": "failed", "error": str(exc)[:300]}
    if status_code == 200:
        return {"status": "sent", "via": "notify_webhook", "detail": body[:300]}
    return {"status": "failed", "error": "http_%s %s" % (status_code, body[:200])}


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> tuple[int, str]:
    """Returns (status_code, body). Follows redirects — the GAS /exec endpoint
    302s to script.googleusercontent.com for the actual response body."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")[:1000]


def _parse_json(body: str) -> Any:
    try:
        return json.loads(body)
    except ValueError:
        return None


def _notify_admin_best_effort(message: str) -> None:
    try:
        import job_runner

        job_runner.notify_admin(message)
    except Exception:  # noqa: BLE001 - admin fallback must never raise
        pass


def _load_contract(run_dir: Path) -> dict[str, Any]:
    for name in ("research_contract.input.json", "research_contract.json"):
        data = _read_json(run_dir / name)
        if isinstance(data, dict):
            return data
    return {}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
