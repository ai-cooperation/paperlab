#!/usr/bin/env python3
"""Detached worker for a v2 engine job (BSIDE_WEB_INTEGRATION_PLAN §3a).

Invoked as a FRESH process (`start_new_session=True`) so a uvicorn redeploy
(`KillMode=process`) cannot kill an in-flight ~30 min run. Runs the full paper
pipeline and — crucially — marks the dossier `failed` (with a traceback tail) on ANY
crash, so `GET /v2/jobs/{id}/status` never sticks on the last phase forever (codex
review 2026-06-16).

Usage: python v2_worker.py <run_dir>   (run_dir holds research_contract.json + dossier.json)
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from framework import Dossier, LiveDispatcher
from packs.paper import pipeline

# Wall-clock watchdog: max_steps is not a time limit (codex). A run that wedges past
# this fires SIGALRM -> TimeoutError -> the dossier is marked failed (never silent).
MAX_WALL_S = int(os.environ.get("V2_MAX_WALL_S", str(120 * 60)))   # default 2h


def _install_watchdog() -> None:
    def _on_alarm(signum, frame):  # noqa: ANN001
        raise TimeoutError(f"wall-clock watchdog: run exceeded {MAX_WALL_S}s")
    signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(MAX_WALL_S)


def _mark(run_dir: Path, run_status: str, **fields) -> None:
    d = Dossier.load(run_dir)
    d.update_status(run_status=run_status, **fields)


def main(run_dir_arg: str) -> int:
    run_dir = Path(run_dir_arg)
    _install_watchdog()
    _mark(run_dir, "running", started_at=int(time.time()))
    try:
        contract = json.loads((run_dir / "research_contract.json").read_text(encoding="utf-8"))
        result = pipeline.run_paper(run_dir, contract, LiveDispatcher(run_dir=run_dir))
        d = Dossier.load(run_dir)
        d.pack_ext_set("run_result", result)
        blocked = result.get("delivery") == "blocked"
        d.update_status(run_status="blocked" if blocked else "done",
                        finished_at=int(time.time()), blocked=blocked)
        return 0
    except Exception as exc:  # noqa: BLE001 - a crash MUST surface as a terminal failed state
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-2000:]
        try:
            d = Dossier.load(run_dir)
            d.pack_ext_set("run_error", tb)
            d.update_status(run_status="failed", phase="failed", finished_at=int(time.time()),
                            blocked=True, blockers=[f"run crashed: {type(exc).__name__}: {exc}"])
        except Exception:  # noqa: BLE001 - never let the failure-marker itself crash silently
            (run_dir / "v2_worker_crash.txt").write_text(tb, encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
