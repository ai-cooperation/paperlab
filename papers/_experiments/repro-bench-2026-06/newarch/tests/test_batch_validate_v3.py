from __future__ import annotations

import pytest

from batch_validate_v3 import JobValidation, decide_batch_gate

pytestmark = pytest.mark.unit


def _row(job_id: str, *, status: str = "done", passed: bool = True) -> JobValidation:
    return JobValidation(
        job_id=job_id,
        status=status,
        passed=passed,
        phases_done=passed,
        gates_done=passed,
        review_ok=passed,
        pdf_ok=passed,
        floor_100=82.0 if passed else None,
        delivery="pass" if passed else "",
        findings=[] if passed else ["failed"],
    )


def test_decide_batch_gate_stops_on_blocked_job():
    decision = decide_batch_gate([_row("v3_a"), _row("v3_b", status="blocked", passed=False)])

    assert decision.passed is False
    assert decision.blocked == 1
    assert decision.failed == 1
    assert "blocked jobs" in decision.reason


def test_decide_batch_gate_passes_all_valid_jobs():
    decision = decide_batch_gate([_row("v3_a"), _row("v3_b")])

    assert decision.passed is True
    assert decision.total == 2
    assert decision.reason == "batch passed"
