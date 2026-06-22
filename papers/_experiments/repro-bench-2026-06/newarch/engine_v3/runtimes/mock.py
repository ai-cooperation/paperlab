from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Optional

from engine_v3.core.contracts import BrainTask, RuntimeContext, TaskResult, WorkerTask


class MockRuntime:
    name = "mock"

    def __init__(self, fail_phases: Optional[Iterable[str]] = None) -> None:
        self.fail_phases = set(fail_phases or [])

    def prepare(self, context: RuntimeContext) -> None:
        context.run_dir.mkdir(parents=True, exist_ok=True)

    def run_brain(self, task: BrainTask, context: RuntimeContext) -> TaskResult:
        return self._run(task.phase, task.expected_outputs, context)

    def run_worker(self, task: WorkerTask, context: RuntimeContext) -> TaskResult:
        return self._run(task.phase, task.expected_outputs, context)

    def review(self, task: BrainTask, context: RuntimeContext) -> TaskResult:
        return self._run(task.phase, task.expected_outputs, context)

    def _run(
        self,
        phase: str,
        expected_outputs: Iterable[str],
        context: RuntimeContext,
    ) -> TaskResult:
        if phase in self.fail_phases:
            return TaskResult(status="failed", details="mock failure: %s" % phase)

        outputs = {}
        for rel in expected_outputs:
            path = context.run_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("mock output for %s\n" % phase, encoding="utf-8")
            outputs[rel] = path
        return TaskResult(
            status="ok",
            outputs=outputs,
            details="mock runtime",
            changed_files=sorted(outputs),
        )
