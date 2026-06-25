from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from engine_v3.core.contracts import BrainTask, RuntimeContext, TaskResult, WorkerTask


@dataclass(frozen=True)
class HermesRunResult:
    exit_code: int
    stdout: str
    stderr: str


HermesRunner = Callable[[list[str], Path, int], HermesRunResult]


class HermesCodexRuntime:
    name = "hermes-codex"

    def __init__(
        self,
        hermes_bin: str = "hermes",
        runner: Optional[HermesRunner] = None,
        timeout_s: int = 1200,
        brain_model: str = "openai-codex",
        brain_provider: Optional[str] = None,
        worker_model: str = "big-pickle",
        worker_provider: str = "custom",
        worker_toolsets: str = "file,terminal",
        skill_root: Optional[Path] = None,
        require_skill_bundle: bool = True,
    ) -> None:
        self.hermes_bin = hermes_bin
        self.runner = runner or _subprocess_runner
        self.timeout_s = timeout_s
        self.brain_model = brain_model
        self.brain_provider = brain_provider
        self.worker_model = worker_model
        self.worker_provider = worker_provider
        self.worker_toolsets = worker_toolsets
        self.skill_root = Path(skill_root).expanduser() if skill_root else None
        self.require_skill_bundle = require_skill_bundle

    def prepare(self, context: RuntimeContext) -> None:
        context.run_dir.mkdir(parents=True, exist_ok=True)

    def run_brain(self, task: BrainTask, context: RuntimeContext) -> TaskResult:
        return self._run(
            task_id=task.task_id,
            phase=task.phase,
            prompt=task.prompt,
            expected_outputs=task.expected_outputs,
            context=context,
            model=self.brain_model,
            provider=self.brain_provider,
            worker_mode=False,
        )

    def run_worker(self, task: WorkerTask, context: RuntimeContext) -> TaskResult:
        return self._run(
            task_id=task.task_id,
            phase=task.phase,
            prompt=task.prompt,
            expected_outputs=task.expected_outputs,
            context=context,
            model=self.worker_model,
            provider=self.worker_provider,
            worker_mode=True,
        )

    def review(self, task: BrainTask, context: RuntimeContext) -> TaskResult:
        return self.run_brain(task, context)

    def _run(
        self,
        *,
        task_id: str,
        phase: str,
        prompt: str,
        expected_outputs: Iterable[str],
        context: RuntimeContext,
        model: str,
        provider: Optional[str],
        worker_mode: bool,
    ) -> TaskResult:
        self.prepare(context)
        missing_skills = _missing_skills(self.skill_root, context.metadata.get("skill_bundle", []))
        if missing_skills and self.require_skill_bundle:
            return TaskResult(
                task_id=task_id,
                status="error",
                details="missing required skill bundle",
                blockers=["missing skill: %s" % skill for skill in missing_skills],
            )
        full_prompt = self._build_prompt(phase, prompt, expected_outputs, context, worker_mode)
        command = [self.hermes_bin, "-z", full_prompt, "-m", model]
        if provider:
            command.extend(["--provider", provider])
        if worker_mode:
            command.extend(["--ignore-rules", "--toolsets", self.worker_toolsets])

        result = self.runner(command, context.run_dir, self.timeout_s)
        combined = "\n".join([result.stdout or "", result.stderr or ""]).strip()
        stdout_tail = _tail(combined)
        provider_failure = _provider_failure(combined)
        if provider_failure:
            return TaskResult(
                task_id=task_id,
                status="error",
                details="provider failure",
                blockers=[provider_failure],
                stdout_tail=stdout_tail,
            )
        if result.exit_code != 0:
            return TaskResult(
                task_id=task_id,
                status="error",
                details="hermes exited with %s" % result.exit_code,
                blockers=[stdout_tail or "hermes failed"],
                stdout_tail=stdout_tail,
            )

        outputs = _existing_outputs(context.run_dir, expected_outputs)
        missing = [rel for rel in expected_outputs if rel not in outputs]
        if missing:
            return TaskResult(
                task_id=task_id,
                status="blocked",
                details="missing declared outputs",
                outputs=outputs,
                changed_files=sorted(outputs),
                blockers=["missing declared output: %s" % rel for rel in missing],
                stdout_tail=stdout_tail,
            )
        return TaskResult(
            task_id=task_id,
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
        worker_mode: bool,
    ) -> str:
        mode = "bounded worker" if worker_mode else "codex brain"
        parts = [
            "Engine v3 Hermes phase: %s (%s)." % (phase, mode),
            _skill_context_reference(self.skill_root, context.metadata.get("skill_bundle", []), context.run_dir),
            prompt,
        ]
        expected = list(expected_outputs)
        if expected:
            parts.append(
                "Write ONLY these files relative to the run directory: "
                + ", ".join(expected)
                + ". End with CHILD_OK."
            )
        else:
            parts.append("End with CHILD_OK.")
        if worker_mode:
            parts.append("You are a child worker. Do not delegate.")
        return "\n\n".join(part for part in parts if part)


def _subprocess_runner(command: list[str], cwd: Path, timeout_s: int) -> HermesRunResult:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    return HermesRunResult(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


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


def _skill_context_reference(skill_root: Optional[Path], skill_bundle: Iterable[str], run_dir: Path) -> str:
    skill_text = _skill_context(skill_root, skill_bundle)
    if not skill_text:
        return ""
    context_path = run_dir / "engine_v3_skill_context.md"
    context_path.write_text(skill_text, encoding="utf-8")
    return (
        "Loaded skill bundle is stored in engine_v3_skill_context.md. "
        "Before acting, read that file and apply every hard requirement relevant to this phase. "
        "Do not proceed from memory or ignore missing/contradictory skill requirements."
    )


def _missing_skills(skill_root: Optional[Path], skill_bundle: Iterable[str]) -> list[str]:
    skills = [str(skill_name) for skill_name in skill_bundle if str(skill_name)]
    if not skills:
        return []
    if skill_root is None:
        return skills
    missing = []
    for skill_name in skills:
        if not (skill_root / skill_name / "SKILL.md").is_file():
            missing.append(skill_name)
    return missing


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
