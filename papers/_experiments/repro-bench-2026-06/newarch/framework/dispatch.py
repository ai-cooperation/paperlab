"""Worker dispatch (DESIGN §3.1, §3.5). Parent-level fan-out only — children
cannot delegate (hermes depth-2). The orchestrator (Python control plane) owns the
fan-out; the brain reasons inside each dispatched unit.

A worker gets a fully SELF-CONTAINED packet (no parent history): verbatim excerpts,
exact metrics, the claim-evidence rows it may rely on, forbidden overclaims, and
isolated read/write file scopes. Two implementations:
  - MockDispatcher  — canned results; the offline control-plane tests use it.
  - HermesDispatcher — shells `hermes -z -m <model>`; LIVE on ac-2012 only
    (delegate_task CHILD_OK was smoke-verified on ac-2012 2026-06-14).
"""
from __future__ import annotations

import json
import subprocess
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

# worker classes (DESIGN §3.1): drafters/fixers = big-pickle; reviewers = strong
# (codex-class) isolated child; external = codex CLI/copilot (model != orchestrator)
WORKER_MODELS = {
    "drafter": "big-pickle",
    "fixer": "big-pickle",
    "reviewer": "openai-codex",
    "external": "codex-cli",
}

# LIVE wiring on ac-2012 (verified 2026-06-15): the free worker tier is the local
# custom endpoint model `deepseek-v4-flash-free` (hermes -z, base 127.0.0.1:8898;
# the config's "big-pickle"->opencode-zen mapping needs a key and is unused). The
# strong brain (reviewers + brain reasoning) is the subscription codex CLI — the
# design's sanctioned path (§3.1) — proven working on alan.chen75.
LIVE_WORKER_MODEL = "deepseek-v4-flash-free"
BRAIN_CLASSES = {"reviewer", "external"}      # routed to codex CLI, not the free worker


@dataclass
class WorkerPacket:
    """Self-contained unit of work (DESIGN §3.5). No parent history -> everything a
    worker needs is in here, or it starves."""
    task_id: str
    role: str
    worker_class: str                       # drafter | fixer | reviewer | external
    task_goal: str
    relevant_excerpts: str = ""             # verbatim, not just file paths
    exact_metrics: dict[str, Any] = field(default_factory=dict)
    claim_evidence_rows: list[dict[str, Any]] = field(default_factory=list)
    no_go_claims: list[str] = field(default_factory=list)
    style_constraints: str = ""
    allowed_files_read: list[str] = field(default_factory=list)
    allowed_files_write: list[str] = field(default_factory=list)
    output_schema: dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: list[str] = field(default_factory=list)
    model: str = ""

    def resolved_model(self) -> str:
        return self.model or WORKER_MODELS.get(self.worker_class, "big-pickle")


@dataclass
class WorkerResult:
    task_id: str
    status: str                              # CHILD_OK | blocked | error
    changed_files: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "CHILD_OK"


class Dispatcher(ABC):
    @abstractmethod
    def delegate(self, packet: WorkerPacket) -> WorkerResult:
        ...


class MockDispatcher(Dispatcher):
    """Records every packet and returns a canned result. The optional `responder`
    lets a test shape the result per packet; default is CHILD_OK."""

    def __init__(self, responder: Callable[[WorkerPacket], WorkerResult] | None = None):
        self.calls: list[WorkerPacket] = []
        self._responder = responder

    def delegate(self, packet: WorkerPacket) -> WorkerResult:
        self.calls.append(packet)
        if self._responder is not None:
            return self._responder(packet)
        return WorkerResult(task_id=packet.task_id, status="CHILD_OK",
                            changed_files=list(packet.allowed_files_write))


class HermesDispatcher(Dispatcher):
    """LIVE worker dispatch on ac-2012: `hermes -z -m <model>` with the packet as a
    self-contained prompt. Not exercised in offline tests — the smoke proof of
    delegate_task CHILD_OK is recorded in DESIGN (ac-2012, 2026-06-14)."""

    def __init__(self, hermes_bin: str = "hermes", run_dir: Path | None = None,
                 timeout_s: int = 1800):
        self.hermes_bin = hermes_bin
        self.run_dir = Path(run_dir) if run_dir else None
        self.timeout_s = timeout_s

    def _prompt(self, packet: WorkerPacket) -> str:
        body = json.dumps(asdict(packet), ensure_ascii=False, indent=2)
        return (
            "You are a BOUNDED worker. You cannot delegate. Read ONLY the files in "
            "allowed_files_read; write ONLY allowed_files_write. Return a concise "
            "completion report ending with the literal token CHILD_OK on success, "
            "or BLOCKED: <reason>.\n\n"
            f"PACKET:\n{body}\n")

    def delegate(self, packet: WorkerPacket) -> WorkerResult:  # pragma: no cover - live only
        cmd = [self.hermes_bin, "-z", self._prompt(packet), "-m", packet.resolved_model(), "--cli"]
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True,
                                  timeout=self.timeout_s,
                                  cwd=str(self.run_dir) if self.run_dir else None)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return WorkerResult(task_id=packet.task_id, status="error",
                                blockers=[f"dispatch failed: {exc}"])
        out = proc.stdout or ""
        if "CHILD_OK" in out:
            return WorkerResult(task_id=packet.task_id, status="CHILD_OK",
                                output={"stdout_tail": out[-2000:]})
        reason = next((ln for ln in out.splitlines() if "BLOCKED" in ln), "no CHILD_OK token")
        return WorkerResult(task_id=packet.task_id, status="blocked", blockers=[reason])


class LiveDispatcher(Dispatcher):
    """LIVE ac-2012 wiring of the NEW design: free workers via hermes, strong brain
    via the codex CLI. drafter/fixer -> `hermes -z -m deepseek-v4-flash-free` (free,
    local endpoint); reviewer/external -> `codex exec` (subscription codex, §3.1).
    This is the hybrid the design sanctions (§3.1 fallback), and it is what makes the
    Hermes path cheap: the bulk (section writing, fixes) runs on the FREE worker, only
    the brain/review judgment spends codex quota."""

    def __init__(self, *, worker_model: str = LIVE_WORKER_MODEL, hermes_bin: str = "hermes",
                 codex_bin: str = "codex", run_dir: Path | None = None,
                 worker_timeout_s: int = 600, brain_timeout_s: int = 1200):
        self.worker_model = worker_model
        self.hermes_bin = hermes_bin
        self.codex_bin = codex_bin
        self.run_dir = Path(run_dir) if run_dir else None
        self.worker_timeout_s = worker_timeout_s
        self.brain_timeout_s = brain_timeout_s

    def _packet_prompt(self, packet: WorkerPacket) -> str:
        return (
            "You are a BOUNDED worker. You cannot delegate. Read ONLY allowed_files_read; "
            "write ONLY allowed_files_write. End with the literal token CHILD_OK on success "
            "or BLOCKED: <reason>.\n\n"
            f"PACKET:\n{json.dumps(asdict(packet), ensure_ascii=False, indent=2)}\n")

    def delegate(self, packet: WorkerPacket) -> WorkerResult:  # pragma: no cover - live only
        cwd = str(self.run_dir) if self.run_dir else None
        prompt = self._packet_prompt(packet)
        if packet.worker_class in BRAIN_CLASSES:
            cmd = [self.codex_bin, "exec", "--skip-git-repo-check",
                   "--sandbox", "workspace-write", prompt]
            timeout = self.brain_timeout_s
        else:
            cmd = [self.hermes_bin, "-z", prompt, "-m", self.worker_model, "--cli"]
            timeout = self.worker_timeout_s
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True,
                                  timeout=timeout, cwd=cwd, stdin=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return WorkerResult(task_id=packet.task_id, status="error",
                                blockers=[f"{packet.worker_class} dispatch failed: {exc}"])
        out = (proc.stdout or "") + (proc.stderr or "")
        if "CHILD_OK" in out or (packet.worker_class in BRAIN_CLASSES and proc.returncode == 0):
            return WorkerResult(task_id=packet.task_id, status="CHILD_OK",
                                changed_files=list(packet.allowed_files_write),
                                output={"stdout_tail": out[-2000:]})
        reason = next((ln for ln in out.splitlines() if "BLOCKED" in ln),
                      f"rc={proc.returncode}, no CHILD_OK")
        return WorkerResult(task_id=packet.task_id, status="blocked", blockers=[reason])
