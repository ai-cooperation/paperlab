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
import os
import signal
import subprocess
import urllib.request
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

# LIVE wiring on ac-2012 (the ORIGINAL pipeline's proven invocation, run_newarch.py
# hermes_short): the free worker is `big-pickle` on the `custom` provider (local
# gateway 127.0.0.1:8898) — invoked as `hermes -z <prompt> --provider custom -m
# big-pickle --ignore-rules --toolsets file,terminal`. The `--provider custom` is
# REQUIRED: without it hermes resolves big-pickle to opencode-zen (which is keyless/
# unused here). The strong brain (reviewers) is the subscription codex CLI (§3.1).
LIVE_WORKER_MODEL = "big-pickle"
LIVE_WORKER_PROVIDER = "custom"
LIVE_WORKER_TOOLSETS = "file,terminal"
# codex can exit 0 while printing a quota/auth error and writing NOTHING — detect
# these so the run fails LOUD instead of proceeding with empty files (garbage output).
CODEX_ERROR_MARKERS = (
    "you've hit your usage limit", "hit your usage limit", "usage limit",
    "payment required", "deactivated_workspace", "upstream_authorization_error",
    "error: unexpected status", "rate limit", "quota",
)
HERMES_VENV_BIN = str(Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "hermes")
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

    def __init__(self, *, worker_model: str = LIVE_WORKER_MODEL, hermes_bin: str = HERMES_VENV_BIN,
                 codex_bin: str = "codex", run_dir: Path | None = None,
                 worker_timeout_s: int = 600, brain_timeout_s: int = 1200):
        self.worker_model = worker_model
        self.hermes_bin = hermes_bin
        self.codex_bin = codex_bin
        self.run_dir = Path(run_dir) if run_dir else None
        self.worker_timeout_s = worker_timeout_s
        self.brain_timeout_s = brain_timeout_s

    def _packet_prompt(self, packet: WorkerPacket) -> str:
        # The task_goal IS the full instruction (the paper-phase prompt). Pass it
        # DIRECTLY — do NOT bury it in a JSON envelope, or a smart brain (codex)
        # treats the wrapper as the task and just echoes CHILD_OK without doing the
        # file write (observed live 2026-06-15). A thin suffix names the outputs.
        parts = [packet.task_goal]
        if packet.relevant_excerpts:
            parts.append("\nContext:\n" + packet.relevant_excerpts)
        if packet.allowed_files_write:
            parts.append(f"\nWrite ONLY these file(s) in the current directory: "
                         f"{', '.join(packet.allowed_files_write)}. Then end with the token CHILD_OK.")
        else:
            parts.append("\nEnd with the token CHILD_OK.")
        return "\n".join(parts)

    def _gateway_healthy(self) -> bool:  # pragma: no cover - live only
        """The free worker lives behind the local gateway; if it's down, drafts
        silently block forever (codex). Probe it and fail LOUD instead."""
        try:
            urllib.request.urlopen("http://127.0.0.1:8898/v1/models", timeout=5)
            return True
        except Exception:  # noqa: BLE001
            return False

    def delegate(self, packet: WorkerPacket) -> WorkerResult:  # pragma: no cover - live only
        cwd = str(self.run_dir) if self.run_dir else None
        prompt = self._packet_prompt(packet)
        is_brain = packet.worker_class in BRAIN_CLASSES
        if is_brain:
            cmd = [self.codex_bin, "exec", "--skip-git-repo-check",
                   "--sandbox", "workspace-write", prompt]
            timeout = self.brain_timeout_s
        else:
            if not self._gateway_healthy():
                return WorkerResult(task_id=packet.task_id, status="error",
                                    blockers=["big-pickle gateway 127.0.0.1:8898 unreachable — "
                                              "fail loud (would otherwise silently block)"])
            # ORIGINAL pipeline's proven big-pickle invocation (run_newarch.hermes_short):
            # --provider custom -> local gateway; --toolsets file,terminal -> can write files.
            cmd = [self.hermes_bin, "-z", prompt, "--provider", LIVE_WORKER_PROVIDER,
                   "-m", self.worker_model, "--ignore-rules", "--toolsets", LIVE_WORKER_TOOLSETS]
            timeout = self.worker_timeout_s
        # Own process group so a timeout kills codex/hermes AND their grandchildren (codex).
        try:
            proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    cwd=cwd, start_new_session=True)
        except OSError as exc:
            return WorkerResult(task_id=packet.task_id, status="error",
                                blockers=[f"{packet.worker_class} spawn failed: {exc}"])
        try:
            out, _ = proc.communicate(timeout=timeout)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)   # kill the whole group
            except (ProcessLookupError, PermissionError):
                proc.kill()
            proc.wait()
            return WorkerResult(task_id=packet.task_id, status="error",
                                blockers=[f"{packet.worker_class} timed out after {timeout}s (group killed)"])
        out = out or ""
        low = out.lower()
        if is_brain and any(m in low for m in CODEX_ERROR_MARKERS):
            line = next((ln for ln in out.splitlines() if "ERROR" in ln or "limit" in ln.lower()),
                        "codex quota/auth error")
            return WorkerResult(task_id=packet.task_id, status="error",
                                blockers=[f"codex unavailable: {line.strip()[:160]}"])
        if "CHILD_OK" in out or (is_brain and rc == 0):
            return WorkerResult(task_id=packet.task_id, status="CHILD_OK",
                                changed_files=list(packet.allowed_files_write),
                                output={"stdout_tail": out[-2000:]})
        reason = next((ln for ln in out.splitlines() if "BLOCKED" in ln), f"rc={rc}, no CHILD_OK")
        return WorkerResult(task_id=packet.task_id, status="blocked", blockers=[reason])
