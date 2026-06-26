"""Configuration loading tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from runtime.config.loader import DEFAULT_CONFIG_PATH, load_runtime_config
from runtime.exceptions import ConfigurationError


def test_load_default_runtime_config() -> None:
    config = load_runtime_config(DEFAULT_CONFIG_PATH)
    assert config.routing.primary == "ollama"
    assert config.tasks_config_path is not None
    assert config.prompts_dir is not None
    assert config.schemas_dir is not None
    assert config.models_config_path is not None


def test_env_override_primary_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_RUNTIME_PRIMARY_PROVIDER", "mock")
    config = load_runtime_config(DEFAULT_CONFIG_PATH)
    assert config.routing.primary == "mock"


def test_missing_config_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ConfigurationError):
        load_runtime_config(missing)


def test_env_interpolation_in_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_RUNTIME_TIMEOUT", "99")
    config_file = tmp_path / "runtime.yaml"
    config_file.write_text(
        """
runtime:
  settings:
    default_timeout_seconds: ${TEST_RUNTIME_TIMEOUT:45}
  routing:
    primary: mock
  providers:
    mock:
      type: mock
      enabled: true
  tasks_config_path: tasks.yaml
  prompts_dir: prompts
  schemas_dir: schemas
  models_config_path: models.yaml
""",
        encoding="utf-8",
    )
    (tmp_path / "tasks.yaml").write_text("tasks: {}\n", encoding="utf-8")
    (tmp_path / "models.yaml").write_text("aliases: {}\n", encoding="utf-8")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "schemas").mkdir()

    config = load_runtime_config(config_file)
    assert config.settings.default_timeout_seconds == 99.0

    monkeypatch.delenv("TEST_RUNTIME_TIMEOUT", raising=False)
    config_default = load_runtime_config(config_file)
    assert config_default.settings.default_timeout_seconds == 45.0
