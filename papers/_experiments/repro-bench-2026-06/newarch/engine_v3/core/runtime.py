from __future__ import annotations

from typing import Protocol

from .contracts import BrainTask, RuntimeContext, TaskResult, WorkerTask


class Runtime(Protocol):
    """Execution boundary for brain and worker agents."""

    name: str

    def prepare(self, context: RuntimeContext) -> None:
        ...

    def run_brain(self, task: BrainTask, context: RuntimeContext) -> TaskResult:
        ...

    def run_worker(self, task: WorkerTask, context: RuntimeContext) -> TaskResult:
        ...

    def review(self, task: BrainTask, context: RuntimeContext) -> TaskResult:
        ...
