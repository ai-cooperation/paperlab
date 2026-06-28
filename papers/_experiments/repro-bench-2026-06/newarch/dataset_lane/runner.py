"""Deterministic analysis executor. The AGENT writes `analysis.py`; PYTHON runs it and
records exactly what ran on what inputs. `real_results.json` is therefore the OUTPUT of
an executed script, not text an LLM wrote — the gates use this record to prove it.

No dataset/column/study is named here.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import schema


def run_analysis(run_dir: Path, *, python: str | None = None, timeout: int = 1800,
                 runner_fn: Any = None) -> dict[str, Any]:
    """Execute `real_experiments/analysis.py --manifest <> --spec <> --out <real_results>`
    with cwd=run_dir, capture stdout/stderr, and write `execution_record.json` with the
    hashes (script/spec/manifest/result) + returncode + start/finish times. `runner_fn`
    is injectable for offline tests (so a test supplies a fake analysis without a real
    subprocess). Returns the execution_record."""
    run_dir = Path(run_dir)
    script = run_dir / schema.ANALYSIS_CODE
    spec = run_dir / schema.ANALYSIS_SPEC
    manifest = run_dir / schema.MANIFEST
    out = run_dir / schema.REAL_RESULTS
    out.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    cmd = [python or sys.executable, str(script),
           "--manifest", str(manifest), "--spec", str(spec), "--out", str(out)]
    if runner_fn is not None:
        rc, so, se = runner_fn(cmd, run_dir)
    elif not script.is_file():
        rc, so, se = 127, "", "analysis.py missing"
    else:
        try:
            proc = subprocess.run(cmd, cwd=str(run_dir), text=True, capture_output=True,
                                  timeout=timeout)
            rc, so, se = proc.returncode, proc.stdout or "", proc.stderr or ""
        except subprocess.TimeoutExpired as exc:
            rc, so, se = 124, exc.stdout or "", f"timeout after {timeout}s"
    finished = time.time()

    (run_dir / schema.ANALYSIS_STDOUT).write_text(so, encoding="utf-8")
    (run_dir / schema.ANALYSIS_STDERR).write_text(se, encoding="utf-8")
    record = {
        "analysis_script_sha256": schema.sha256_file(script) if script.is_file() else None,
        "analysis_spec_sha256": schema.sha256_file(spec) if spec.is_file() else None,
        "manifest_sha256": schema.sha256_file(manifest) if manifest.is_file() else None,
        "real_results_sha256": schema.sha256_file(out) if out.is_file() else None,
        "real_results_mtime_unix": out.stat().st_mtime if out.is_file() else None,
        "returncode": rc,
        "started_at_unix": started,
        "finished_at_unix": finished,
        "stdout_path": schema.ANALYSIS_STDOUT,
        "stderr_path": schema.ANALYSIS_STDERR,
        "stdout_tail": so[-2000:],
        "stderr_tail": se[-2000:],
    }
    schema.write_json(run_dir, schema.EXECUTION_RECORD, record)
    return record
