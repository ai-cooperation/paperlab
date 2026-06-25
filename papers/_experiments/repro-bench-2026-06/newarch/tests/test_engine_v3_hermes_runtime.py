from __future__ import annotations

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
