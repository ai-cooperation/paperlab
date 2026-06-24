from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from engine_v3.core.contracts import BrainTask, RuntimeContext, TaskResult, WorkerTask


@dataclass(frozen=True)
class CliRunResult:
    exit_code: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str], Path, int], CliRunResult]


class CodexCliRuntime:
    name = "codex-cli"

    def __init__(
        self,
        command: str = "codex",
        runner: Optional[CommandRunner] = None,
        timeout_s: int = 1200,
        skill_root: Optional[Path] = None,
    ) -> None:
        self.command = command
        self.runner = runner or _subprocess_runner
        self.timeout_s = timeout_s
        self.skill_root = Path(skill_root).expanduser() if skill_root else None

    def prepare(self, context: RuntimeContext) -> None:
        context.run_dir.mkdir(parents=True, exist_ok=True)

    def run_brain(self, task: BrainTask, context: RuntimeContext) -> TaskResult:
        return self._run(task.phase, task.prompt, task.expected_outputs, context)

    def run_worker(self, task: WorkerTask, context: RuntimeContext) -> TaskResult:
        return self._run(task.phase, task.prompt, task.expected_outputs, context)

    def review(self, task: BrainTask, context: RuntimeContext) -> TaskResult:
        return self._run(task.phase, task.prompt, task.expected_outputs, context)

    def _run(
        self,
        phase: str,
        prompt: str,
        expected_outputs: Iterable[str],
        context: RuntimeContext,
    ) -> TaskResult:
        self.prepare(context)
        full_prompt = self._build_prompt(phase, prompt, expected_outputs, context)
        command = [
            self.command,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            full_prompt,
        ]
        result = self.runner(command, context.run_dir, self.timeout_s)
        combined = "\n".join([result.stdout or "", result.stderr or ""]).strip()
        stdout_tail = _tail(combined)
        provider_failure = _provider_failure(combined)
        if provider_failure:
            return TaskResult(
                status="error",
                details="provider failure",
                blockers=[provider_failure],
                stdout_tail=stdout_tail,
            )
        if result.exit_code != 0:
            return TaskResult(
                status="error",
                details="codex cli exited with %s" % result.exit_code,
                blockers=[stdout_tail or "codex cli failed"],
                stdout_tail=stdout_tail,
            )

        outputs = _existing_outputs(context.run_dir, expected_outputs)
        missing = [
            rel for rel in expected_outputs
            if rel not in outputs
        ]
        if missing:
            return TaskResult(
                status="blocked",
                details="missing declared outputs",
                outputs=outputs,
                changed_files=sorted(outputs),
                blockers=["missing declared output: %s" % rel for rel in missing],
                stdout_tail=stdout_tail,
            )
        return TaskResult(
            status="ok",
            outputs=outputs,
            changed_files=sorted(outputs),
            stdout_tail=stdout_tail,
        )

    def _build_prompt(
        self,
        phase: str,
        prompt: str,
        expected_outputs: Iterable[str],
        context: RuntimeContext,
    ) -> str:
        parts = [
            "Engine v3 phase: %s" % phase,
            _skill_context(self.skill_root, context.metadata.get("skill_bundle", [])),
            prompt,
        ]
        expected = list(expected_outputs)
        if expected:
            parts.append(
                "Declared outputs: write these files relative to the run directory: "
                + ", ".join(expected)
            )
        return "\n\n".join(part for part in parts if part)


def _subprocess_runner(command: list[str], cwd: Path, timeout_s: int) -> CliRunResult:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    return CliRunResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def _existing_outputs(run_dir: Path, expected_outputs: Iterable[str]) -> dict[str, Path]:
    outputs = {}
    for rel in expected_outputs:
        path = run_dir / rel
        if path.is_file():
            outputs[rel] = path
    return outputs


def _skill_context(skill_root: Optional[Path], skill_bundle: Iterable[str]) -> str:
    if skill_root is None:
        return ""
    blocks = []
    for skill_name in skill_bundle:
        skill_path = skill_root / str(skill_name) / "SKILL.md"
        if skill_path.is_file():
            blocks.append(
                "Skill %s:\n%s" % (
                    skill_name,
                    skill_path.read_text(encoding="utf-8"),
                )
            )
        else:
            blocks.append("Missing skill %s at %s" % (skill_name, skill_path))
    if not blocks:
        return ""
    return "Loaded skill bundle:\n\n" + "\n\n".join(blocks)


def _provider_failure(output: str) -> str:
    low = output.lower()
    patterns = [
        "usage limit",
        "quota",
        "authentication",
        "auth failed",
        "rate limit",
        "provider unavailable",
        "provider failure",
    ]
    for pattern in patterns:
        if pattern in low:
            return _tail(output) or pattern
    return ""


def _tail(text: str, max_chars: int = 2000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]
