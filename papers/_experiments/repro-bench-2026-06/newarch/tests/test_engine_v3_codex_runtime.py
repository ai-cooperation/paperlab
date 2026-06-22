from __future__ import annotations

from pathlib import Path

import pytest

from engine_v3.core import BrainTask, RuntimeContext
from engine_v3.runtimes.codex_cli import CliRunResult, CodexCliRuntime

pytestmark = pytest.mark.unit


def test_codex_runtime_returns_ok_only_when_declared_outputs_exist(tmp_path: Path):
    def runner(command, cwd: Path, timeout_s: int):
        (cwd / "sections" / "intro.md").parent.mkdir(parents=True)
        (cwd / "sections" / "intro.md").write_text("intro", encoding="utf-8")
        return CliRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = CodexCliRuntime(runner=runner)
    task = BrainTask(phase="write", prompt="write intro", expected_outputs=["sections/intro.md"])

    result = runtime.run_brain(task, RuntimeContext(job_id="job-1", run_dir=tmp_path))

    assert result.status == "ok"
    assert result.changed_files == ["sections/intro.md"]
    assert result.outputs == {"sections/intro.md": tmp_path / "sections/intro.md"}


def test_codex_runtime_blocks_when_declared_outputs_are_missing(tmp_path: Path):
    runtime = CodexCliRuntime(
        runner=lambda _command, _cwd, _timeout_s: CliRunResult(
            exit_code=0,
            stdout="CHILD_OK",
            stderr="",
        )
    )
    task = BrainTask(phase="write", prompt="write intro", expected_outputs=["sections/intro.md"])

    result = runtime.run_brain(task, RuntimeContext(job_id="job-1", run_dir=tmp_path))

    assert result.status == "blocked"
    assert result.blockers == ["missing declared output: sections/intro.md"]


@pytest.mark.parametrize(
    "message",
    [
        "usage limit reached",
        "authentication failed",
        "rate limit exceeded",
        "provider unavailable",
    ],
)
def test_codex_runtime_classifies_provider_failures_as_error(tmp_path: Path, message: str):
    runtime = CodexCliRuntime(
        runner=lambda _command, _cwd, _timeout_s: CliRunResult(
            exit_code=0,
            stdout=message,
            stderr="",
        )
    )

    result = runtime.run_brain(
        BrainTask(phase="review", prompt="review", expected_outputs=[]),
        RuntimeContext(job_id="job-1", run_dir=tmp_path),
    )

    assert result.status == "error"
    assert result.blockers == [message]


def test_codex_runtime_loads_declared_skill_files(tmp_path: Path):
    skill_root = tmp_path / "skills"
    skill_dir = skill_root / "paper-draft"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("paper draft rules", encoding="utf-8")
    seen = {}

    def runner(command, cwd: Path, timeout_s: int):
        seen["prompt"] = command[-1]
        return CliRunResult(exit_code=0, stdout="CHILD_OK", stderr="")

    runtime = CodexCliRuntime(runner=runner, skill_root=skill_root)
    context = RuntimeContext(
        job_id="job-1",
        run_dir=tmp_path,
        metadata={"skill_bundle": ["paper-draft"]},
    )

    result = runtime.run_brain(BrainTask(phase="gap", prompt="find gap"), context)

    assert result.status == "ok"
    assert "paper draft rules" in seen["prompt"]
