from __future__ import annotations

import stat
import time
from pathlib import Path

import pytest

from engine_v3.core import BrainTask, RuntimeContext, WorkerTask
from engine_v3.runtimes.hermes import HermesCodexRuntime, HermesRunResult

pytestmark = pytest.mark.unit


def test_hermes_runtime_brain_writes_declared_file(tmp_path: Path):
    seen = {}

    def runner(command: list[str], cwd: Path, timeout_s: int):
        seen["command"] = command
        (cwd / "gap.md").write_text("gap", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner)
    result = runtime.run_brain(
        BrainTask(phase="gap", prompt="write gap", expected_outputs=["gap.md"]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert result.changed_files == ["gap.md"]
    assert "openai-codex" in seen["command"]


def test_hermes_runtime_worker_uses_big_pickle_and_writes_declared_file(tmp_path: Path):
    seen = {}

    def runner(command: list[str], cwd: Path, timeout_s: int):
        seen["command"] = command
        (cwd / "sections" / "intro.md").parent.mkdir(parents=True)
        (cwd / "sections" / "intro.md").write_text("intro", encoding="utf-8")
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner)
    result = runtime.run_worker(
        WorkerTask(phase="write", prompt="write intro", expected_outputs=["sections/intro.md"]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert result.changed_files == ["sections/intro.md"]
    assert "big-pickle" in seen["command"]
    assert "--toolsets" in seen["command"]


def test_hermes_runtime_loads_pack_skill_bundle(tmp_path: Path):
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "paper-draft"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("paper rules", encoding="utf-8")
    seen = {}

    def runner(command: list[str], cwd: Path, timeout_s: int):
        seen["prompt"] = command[command.index("-z") + 1]
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner, skill_root=skill_root)
    result = runtime.run_brain(
        BrainTask(phase="review", prompt="review"),
        RuntimeContext(
            job_id="job-1",
            run_dir=tmp_path,
            metadata={"skill_bundle": ["paper-draft"]},
        ),
    )

    assert result.status == "ok"
    assert "engine_v3_skill_context.md" in seen["prompt"]
    assert "paper rules" not in seen["prompt"]
    assert (tmp_path / "engine_v3_skill_context.md").read_text(encoding="utf-8").count("paper rules") == 1


def test_hermes_runtime_keeps_large_skill_bundle_out_of_argv(tmp_path: Path):
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "qmd-writer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("table rule\n" * 10000, encoding="utf-8")
    seen = {}

    def runner(command: list[str], cwd: Path, timeout_s: int):
        seen["prompt"] = command[command.index("-z") + 1]
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner, skill_root=skill_root)
    result = runtime.run_brain(
        BrainTask(phase="review", prompt="review"),
        RuntimeContext(
            job_id="job-1",
            run_dir=tmp_path,
            metadata={"skill_bundle": ["qmd-writer"]},
        ),
    )

    assert result.status == "ok"
    assert len(seen["prompt"]) < 1000
    assert "table rule" not in seen["prompt"]
    assert (tmp_path / "engine_v3_skill_context.md").stat().st_size > 100_000


def test_hermes_runtime_errors_when_declared_skill_is_missing(tmp_path: Path):
    called = False

    def runner(_command: list[str], _cwd: Path, _timeout_s: int):
        nonlocal called
        called = True
        return HermesRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = HermesCodexRuntime(runner=runner)
    result = runtime.run_brain(
        BrainTask(phase="write", prompt="write"),
        RuntimeContext(
            job_id="job-1",
            run_dir=tmp_path,
            metadata={"skill_bundle": ["qmd-writer"]},
        ),
    )

    assert result.status == "error"
    assert result.blockers == ["missing skill: qmd-writer"]
    assert called is False


@pytest.mark.parametrize(
    "message",
    [
        "usage limit reached",
        "authentication failed",
        "rate limit exceeded",
        "provider unavailable",
    ],
)
def test_hermes_runtime_classifies_provider_failures_as_error(tmp_path: Path, message: str):
    runtime = HermesCodexRuntime(
        runner=lambda _command, _cwd, _timeout_s: HermesRunResult(
            exit_code=0,
            stdout=message,
            stderr="",
        )
    )

    result = runtime.run_brain(
        BrainTask(phase="review", prompt="review"),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "error"
    assert result.blockers == [message]


def test_hermes_runtime_blocks_when_declared_output_missing(tmp_path: Path):
    runtime = HermesCodexRuntime(
        runner=lambda _command, _cwd, _timeout_s: HermesRunResult(
            exit_code=0,
            stdout="CHILD_OK",
            stderr="",
        )
    )

    result = runtime.run_worker(
        WorkerTask(phase="write", prompt="write", expected_outputs=["missing.md"]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    assert result.blockers == ["missing declared output: missing.md"]


def test_hermes_runtime_finishes_when_outputs_exist_but_process_hangs(tmp_path: Path):
    hermes_bin = tmp_path / "hermes-stub"
    hermes_bin.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import time
Path("done.md").write_text("done", encoding="utf-8")
time.sleep(30)
""",
        encoding="utf-8",
    )
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)

    runtime = HermesCodexRuntime(
        hermes_bin=str(hermes_bin),
        timeout_s=10,
        output_complete_grace_s=0.1,
    )

    started = time.monotonic()
    result = runtime.run_brain(
        BrainTask(phase="data", prompt="write", expected_outputs=["done.md"]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "ok"
    assert result.changed_files == ["done.md"]
    assert time.monotonic() - started < 5
    assert "terminated after all declared outputs existed" in result.stdout_tail


def test_hermes_runtime_unblocks_when_partial_outputs_stop_changing(tmp_path: Path):
    hermes_bin = tmp_path / "hermes-stub"
    hermes_bin.write_text(
        """#!/usr/bin/env python3
from pathlib import Path
import time
Path("references.bib").write_text("@article{x, title={x}}", encoding="utf-8")
time.sleep(30)
""",
        encoding="utf-8",
    )
    hermes_bin.chmod(hermes_bin.stat().st_mode | stat.S_IXUSR)

    runtime = HermesCodexRuntime(
        hermes_bin=str(hermes_bin),
        timeout_s=10,
        output_complete_grace_s=0.1,
        output_partial_idle_s=0.1,
    )

    started = time.monotonic()
    result = runtime.run_brain(
        BrainTask(
            phase="data",
            prompt="write",
            expected_outputs=["references.bib", "figures/fig_forest_plot.svg"],
        ),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "blocked"
    assert result.changed_files == ["references.bib"]
    assert result.blockers == ["missing declared output: figures/fig_forest_plot.svg"]
    assert time.monotonic() - started < 5
    assert "terminated after partial declared outputs stopped changing" in result.stdout_tail
