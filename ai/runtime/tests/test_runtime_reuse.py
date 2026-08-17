"""AIRuntime is reused for the same resolved config key."""
from __future__ import annotations

from pathlib import Path

from runtime.config.loader import DEFAULT_CONFIG_PATH
from runtime.core import runtime as runtime_module
from runtime.core.runtime import get_runtime, reset_runtime


def test_same_resolved_path_reuses_runtime():
    reset_runtime()
    a = get_runtime(DEFAULT_CONFIG_PATH)
    b = get_runtime(DEFAULT_CONFIG_PATH)
    c = get_runtime(Path(str(DEFAULT_CONFIG_PATH)))
    assert a is b
    assert b is c
    reset_runtime()


def test_reset_runtime_recreates():
    reset_runtime()
    a = get_runtime(DEFAULT_CONFIG_PATH)
    reset_runtime()
    b = get_runtime(DEFAULT_CONFIG_PATH)
    assert a is not b
    reset_runtime()


def test_none_and_same_env_path_reuse(monkeypatch):
    reset_runtime()
    monkeypatch.setenv('AI_RUNTIME_CONFIG', str(DEFAULT_CONFIG_PATH))
    a = get_runtime(None)
    b = get_runtime(DEFAULT_CONFIG_PATH)
    assert a is b
    reset_runtime()


def test_runtime_cache_is_bounded():
    reset_runtime()
    first = get_runtime(DEFAULT_CONFIG_PATH)
    again = get_runtime(DEFAULT_CONFIG_PATH)
    assert first is again
    assert len(runtime_module._RUNTIMES) == 1
    assert runtime_module._MAX_RUNTIMES >= 1
    reset_runtime()
