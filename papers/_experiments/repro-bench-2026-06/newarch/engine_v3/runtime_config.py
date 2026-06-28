from __future__ import annotations

import os
from pathlib import Path

from engine_v3.runtimes import CodexCliRuntime, HermesCodexRuntime, MockRuntime


RUNTIME_ENV = "PAPER_ENGINE_V3_RUNTIME"
SKILL_ROOT_ENV = "PAPER_ENGINE_V3_SKILL_ROOT"
HERMES_BIN_ENV = "PAPER_ENGINE_V3_HERMES_BIN"
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
