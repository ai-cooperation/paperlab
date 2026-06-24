from __future__ import annotations

import pytest

from engine_v3.runtime_config import runtime_from_env
from engine_v3.runtimes import CodexCliRuntime, HermesCodexRuntime, MockRuntime

pytestmark = pytest.mark.unit


def test_runtime_from_env_defaults_to_codex_cli(monkeypatch):
    monkeypatch.delenv("PAPER_ENGINE_V3_RUNTIME", raising=False)

    assert isinstance(runtime_from_env(), CodexCliRuntime)


def test_runtime_from_env_selects_hermes(monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "hermes-codex")

    assert isinstance(runtime_from_env(), HermesCodexRuntime)


def test_runtime_from_env_selects_mock(monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "mock")

    assert isinstance(runtime_from_env(), MockRuntime)


def test_runtime_from_env_rejects_unknown(monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "unknown")

    with pytest.raises(ValueError, match="unknown engine v3 runtime"):
        runtime_from_env()
