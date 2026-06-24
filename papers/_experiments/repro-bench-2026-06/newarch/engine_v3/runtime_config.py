from __future__ import annotations

import os

from engine_v3.runtimes import CodexCliRuntime, HermesCodexRuntime, MockRuntime


RUNTIME_ENV = "PAPER_ENGINE_V3_RUNTIME"
DEFAULT_RUNTIME = "hermes-codex"


def runtime_from_env():
    name = os.environ.get(RUNTIME_ENV, DEFAULT_RUNTIME).strip().lower()
    if name in ("codex", "codex-cli"):
        return CodexCliRuntime()
    if name in ("hermes", "hermes-codex"):
        return HermesCodexRuntime()
    if name == "mock":
        return MockRuntime()
    raise ValueError("unknown engine v3 runtime: %s" % name)
