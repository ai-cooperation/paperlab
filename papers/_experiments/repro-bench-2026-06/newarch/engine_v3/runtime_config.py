from __future__ import annotations

import os
from pathlib import Path

from engine_v3.runtimes import CodexCliRuntime, HermesCodexRuntime, MockRuntime


RUNTIME_ENV = "PAPER_ENGINE_V3_RUNTIME"
SKILL_ROOT_ENV = "PAPER_ENGINE_V3_SKILL_ROOT"
HERMES_BIN_ENV = "PAPER_ENGINE_V3_HERMES_BIN"
HERMES_TIMEOUT_ENV = "PAPER_ENGINE_V3_HERMES_TIMEOUT_S"
HERMES_OUTPUT_COMPLETE_GRACE_ENV = "PAPER_ENGINE_V3_HERMES_OUTPUT_COMPLETE_GRACE_S"
HERMES_OUTPUT_STARTUP_IDLE_ENV = "PAPER_ENGINE_V3_HERMES_OUTPUT_STARTUP_IDLE_S"
HERMES_OUTPUT_PARTIAL_IDLE_ENV = "PAPER_ENGINE_V3_HERMES_OUTPUT_PARTIAL_IDLE_S"
DEFAULT_RUNTIME = "hermes-codex"
DEFAULT_SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills"


def runtime_from_env():
    name = os.environ.get(RUNTIME_ENV, DEFAULT_RUNTIME).strip().lower()
    if name in ("codex", "codex-cli"):
        return CodexCliRuntime()
    if name in ("hermes", "hermes-codex"):
        return HermesCodexRuntime(
            hermes_bin=hermes_bin_from_env(),
            skill_root=skill_root_from_env(),
            timeout_s=_int_env(HERMES_TIMEOUT_ENV, 1200),
            output_complete_grace_s=_float_env(HERMES_OUTPUT_COMPLETE_GRACE_ENV, 60.0),
            output_startup_idle_s=_float_env(HERMES_OUTPUT_STARTUP_IDLE_ENV, 600.0),
            output_partial_idle_s=_float_env(HERMES_OUTPUT_PARTIAL_IDLE_ENV, 180.0),
        )
    if name == "mock":
        return MockRuntime()
    raise ValueError("unknown engine v3 runtime: %s" % name)


def skill_root_from_env() -> Path | None:
    raw = os.environ.get(SKILL_ROOT_ENV, "").strip()
    if raw:
        return Path(raw).expanduser()
    if DEFAULT_SKILL_ROOT.is_dir():
        return DEFAULT_SKILL_ROOT
    return None


def hermes_bin_from_env() -> str:
    raw = os.environ.get(HERMES_BIN_ENV, "").strip()
    if raw:
        return str(Path(raw).expanduser())
    local_bin = Path.home() / ".local" / "bin" / "hermes"
    if local_bin.is_file():
        return str(local_bin)
    return "hermes"


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)
