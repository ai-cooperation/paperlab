from __future__ import annotations

import pytest

from engine_v3.runtime_config import runtime_from_env
from engine_v3.runtimes import CodexCliRuntime, HermesCodexRuntime, MockRuntime

pytestmark = pytest.mark.unit


def test_runtime_from_env_defaults_to_hermes_codex(monkeypatch):
    monkeypatch.delenv("PAPER_ENGINE_V3_RUNTIME", raising=False)

    assert isinstance(runtime_from_env(), HermesCodexRuntime)


def test_runtime_from_env_passes_skill_root_to_hermes(monkeypatch, tmp_path):
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "hermes-codex")
    monkeypatch.setenv("PAPER_ENGINE_V3_SKILL_ROOT", str(tmp_path))

    runtime = runtime_from_env()

    assert isinstance(runtime, HermesCodexRuntime)
    assert runtime.skill_root == tmp_path


def test_runtime_from_env_passes_hermes_bin_override(monkeypatch, tmp_path):
    hermes_bin = tmp_path / "hermes"
    hermes_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "hermes-codex")
    monkeypatch.setenv("PAPER_ENGINE_V3_HERMES_BIN", str(hermes_bin))

    runtime = runtime_from_env()

    assert isinstance(runtime, HermesCodexRuntime)
    assert runtime.hermes_bin == str(hermes_bin)


def test_runtime_from_env_passes_hermes_timeout_bounds(monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "hermes-codex")
    monkeypatch.setenv("PAPER_ENGINE_V3_HERMES_TIMEOUT_S", "321")
    monkeypatch.setenv("PAPER_ENGINE_V3_HERMES_OUTPUT_STARTUP_IDLE_S", "12.5")
    monkeypatch.setenv("PAPER_ENGINE_V3_HERMES_OUTPUT_PARTIAL_IDLE_S", "13.5")
    monkeypatch.setenv("PAPER_ENGINE_V3_HERMES_OUTPUT_COMPLETE_GRACE_S", "2.5")

    runtime = runtime_from_env()

    assert isinstance(runtime, HermesCodexRuntime)
    assert runtime.timeout_s == 321
    assert runtime.output_startup_idle_s == 12.5
    assert runtime.output_partial_idle_s == 13.5
    assert runtime.output_complete_grace_s == 2.5


def test_runtime_from_env_selects_codex_only_when_explicit(monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "codex-cli")

    assert isinstance(runtime_from_env(), CodexCliRuntime)


def test_runtime_from_env_selects_mock(monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "mock")

    assert isinstance(runtime_from_env(), MockRuntime)


def test_runtime_from_env_rejects_unknown(monkeypatch):
    monkeypatch.setenv("PAPER_ENGINE_V3_RUNTIME", "unknown")

    with pytest.raises(ValueError, match="unknown engine v3 runtime"):
        runtime_from_env()
