"""Ollama provider integration tests with the AI runtime."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from runtime.config.loader import load_runtime_config
from runtime.core.runtime import AIRuntime
from runtime.exceptions import RetryExhaustedError
from providers.factory import ProviderFactory
from providers.ollama import OllamaProvider
from providers.ollama.client import OllamaClient
from providers.ollama.tests.conftest import (
    JD_RESPONSE,
    RESUME_RESPONSE,
    build_ollama_mock_transport,
)
from runtime.registry.model_registry import ModelRegistry


def _runtime_config_path(tmp_path: Path) -> Path:
    config_file = tmp_path / "runtime.yaml"
    ai_root = Path(__file__).resolve().parents[3]
    runtime_root = ai_root / "runtime"
    config_file.write_text(
        f"""
runtime:
  settings:
    default_timeout_seconds: 30
  routing:
    primary: ollama
    fallback_chain: []
  providers:
    ollama:
      type: ollama
      enabled: true
      base_url: http://ollama.test
      default_timeout_seconds: 30
  retry:
    max_attempts: 1
  tasks_config_path: {runtime_root / "config" / "tasks.default.yaml"}
  capabilities_dir: {ai_root / "capabilities"}
  models_config_path: {runtime_root / "config" / "models.default.yaml"}
""",
        encoding="utf-8",
    )
    return config_file


def _patch_ollama_client(chat_content: dict | str = RESUME_RESPONSE):
    transport = build_ollama_mock_transport(chat_content=chat_content)
    http_client = httpx.Client(transport=transport, base_url="http://ollama.test")

    def factory(config, provider_id):
        return OllamaClient(config, provider_id=provider_id, http_client=http_client)

    return patch("providers.ollama.provider.OllamaClient", side_effect=factory)


def test_factory_creates_ollama_provider() -> None:
    provider = ProviderFactory.create(
        "ollama",
        {"type": "ollama", "enabled": True, "base_url": "http://localhost:11434"},
    )
    assert isinstance(provider, OllamaProvider)
    assert provider.provider_id == "ollama"


def test_runtime_run_task_resume_parsing(tmp_path: Path) -> None:
    config_file = _runtime_config_path(tmp_path)
    with _patch_ollama_client(RESUME_RESPONSE):
        runtime = AIRuntime(load_runtime_config(config_file))
        result = runtime.run_task("resume_parsing", "Senior Python Engineer resume")
    assert result.task == "resume_parsing"
    assert result.provider_id == "ollama"
    assert result.model == "qwen2.5:7b-instruct"
    assert result.validation_passed is True
    assert result.output["type"] == "resume"


def test_runtime_run_task_jd_parsing(tmp_path: Path) -> None:
    config_file = _runtime_config_path(tmp_path)
    with _patch_ollama_client(JD_RESPONSE):
        runtime = AIRuntime(load_runtime_config(config_file))
        result = runtime.run_task("jd_parsing", "Backend engineer role")
    assert result.task == "jd_parsing"
    assert result.provider_id == "ollama"
    assert isinstance(result.output, dict)


def test_runtime_health_refresh(tmp_path: Path) -> None:
    config_file = _runtime_config_path(tmp_path)
    with _patch_ollama_client():
        runtime = AIRuntime(load_runtime_config(config_file))
        statuses = runtime.refresh_health()
    assert len(statuses) >= 1
    assert statuses[0].provider_id == "ollama"
    assert statuses[0].available is True


def test_runtime_fails_when_ollama_unavailable(tmp_path: Path) -> None:
    config_file = _runtime_config_path(tmp_path)
    transport = build_ollama_mock_transport(chat_status=503, tags_status=503)

    def failing_client(config, provider_id):
        http_client = httpx.Client(transport=transport, base_url="http://ollama.test")
        return OllamaClient(config, provider_id=provider_id, http_client=http_client)

    with patch("providers.ollama.provider.OllamaClient", side_effect=failing_client):
        runtime = AIRuntime(load_runtime_config(config_file))
        with pytest.raises(RetryExhaustedError):
            runtime.run_task("resume_parsing", "should fail")


def test_model_alias_resolution_from_config(tmp_path: Path) -> None:
    config_file = _runtime_config_path(tmp_path)
    runtime = AIRuntime(load_runtime_config(config_file))
    resolved = runtime.models.resolve("resume-parser", provider_id="ollama")
    assert resolved == "qwen2.5:7b-instruct"


def test_structured_output_schema_validation(tmp_path: Path) -> None:
    config_file = _runtime_config_path(tmp_path)
    invalid = {"type": "resume", "person": {"name": "Jane"}}
    with _patch_ollama_client(invalid):
        runtime = AIRuntime(load_runtime_config(config_file))
        with pytest.raises(Exception):
            runtime.run_task("resume_parsing", "invalid schema output")


def test_no_provider_available_raises_clearly(tmp_path: Path) -> None:
    config_file = tmp_path / "runtime.yaml"
    ai_root = Path(__file__).resolve().parents[3]
    runtime_root = ai_root / "runtime"
    config_file.write_text(
        f"""
runtime:
  routing:
    primary: ollama
  providers:
    ollama:
      type: ollama
      enabled: false
      base_url: http://ollama.test
  tasks_config_path: {runtime_root / "config" / "tasks.default.yaml"}
  capabilities_dir: {ai_root / "capabilities"}
  models_config_path: {runtime_root / "config" / "models.default.yaml"}
""",
        encoding="utf-8",
    )
    runtime = AIRuntime(load_runtime_config(config_file))
    with pytest.raises(Exception, match="No healthy configured providers"):
        runtime.run_task("resume_parsing", "no provider")
