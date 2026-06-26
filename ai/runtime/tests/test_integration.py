"""Runtime integration tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from runtime.config.loader import load_runtime_config
from runtime.core.runtime import AIRuntime, run_task
from runtime.exceptions import RetryExhaustedError
from runtime.providers.ollama.client import OllamaClient
from runtime.providers.ollama.tests.conftest import (
    JD_RESPONSE,
    RESUME_RESPONSE,
    build_ollama_mock_transport,
)


def test_run_task_resume_parsing(runtime: AIRuntime) -> None:
    result = runtime.run_task("resume_parsing", "Senior Python Engineer resume")
    assert result.task == "resume_parsing"
    assert result.provider_id == "ollama"
    assert result.validation_passed is True
    assert result.output["type"] == "resume"


def test_run_task_module_api(runtime: AIRuntime) -> None:
    with patch(
        "runtime.providers.ollama.provider.OllamaClient",
        side_effect=lambda config, provider_id: OllamaClient(
            config,
            provider_id=provider_id,
            http_client=httpx.Client(
                transport=build_ollama_mock_transport(chat_content=JD_RESPONSE),
                base_url=config.base_url,
            ),
        ),
    ):
        result = run_task("jd_parsing", "Backend engineer role")
    assert result.task == "jd_parsing"
    assert isinstance(result.output, dict)


def test_run_task_text_output_task(runtime: AIRuntime) -> None:
    with patch(
        "runtime.providers.ollama.provider.OllamaClient",
        side_effect=lambda config, provider_id: OllamaClient(
            config,
            provider_id=provider_id,
            http_client=httpx.Client(
                transport=build_ollama_mock_transport(chat_content="Concise professional summary."),
                base_url=config.base_url,
            ),
        ),
    ):
        result = runtime.run_task("resume_summary", "Long resume content")
    assert result.task == "resume_summary"
    assert isinstance(result.output, str)
    assert len(result.output) > 0


def test_metrics_recorded(runtime: AIRuntime) -> None:
    runtime.metrics.reset()
    runtime.run_task("resume_parsing", "metrics test")
    summary = runtime.metrics.summary()
    assert summary["total_tasks"] == 1
    assert summary["success_rate"] == 1.0


def test_health_refresh(runtime: AIRuntime) -> None:
    statuses = runtime.refresh_health()
    assert len(statuses) >= 1
    assert statuses[0].available is True


def test_retry_and_fallback(tmp_path: Path) -> None:
    config_file = tmp_path / "runtime.yaml"
    config_file.write_text(
        f"""
runtime:
  settings:
    default_timeout_seconds: 5
  routing:
    primary: mock_primary
    fallback_chain: [mock_fallback]
  providers:
    mock_primary:
      type: mock
      enabled: true
      default_latency_ms: 0
      always_succeed: false
    mock_fallback:
      type: mock
      enabled: true
      default_latency_ms: 0
      always_succeed: true
      responses:
        resume_parsing:
          type: resume
          person:
            name: Fallback Candidate
            email: fallback@example.com
            phone: "555-0199"
          skills: []
          experience: []
          education: []
  retry:
    max_attempts: 1
  tasks_config_path: {Path(__file__).resolve().parents[1] / "config" / "tasks.default.yaml"}
  capabilities_dir: {Path(__file__).resolve().parents[2] / "capabilities"}
  prompts_dir: {Path(__file__).resolve().parents[1] / "prompts" / "definitions"}
  schemas_dir: {Path(__file__).resolve().parents[1] / "schemas" / "definitions"}
  models_config_path: {Path(__file__).resolve().parents[1] / "config" / "models.default.yaml"}
""",
        encoding="utf-8",
    )
    runtime = AIRuntime(load_runtime_config(config_file))
    result = runtime.run_task("resume_parsing", "fallback test")
    assert result.provider_id == "mock_fallback"
    assert result.fallbacks_used >= 1


def test_retry_exhausted(tmp_path: Path) -> None:
    config_file = tmp_path / "runtime.yaml"
    config_file.write_text(
        f"""
runtime:
  routing:
    primary: mock
  providers:
    mock:
      type: mock
      enabled: true
      default_latency_ms: 0
      always_succeed: false
  retry:
    max_attempts: 2
  tasks_config_path: {Path(__file__).resolve().parents[1] / "config" / "tasks.default.yaml"}
  capabilities_dir: {Path(__file__).resolve().parents[2] / "capabilities"}
  prompts_dir: {Path(__file__).resolve().parents[1] / "prompts" / "definitions"}
  schemas_dir: {Path(__file__).resolve().parents[1] / "schemas" / "definitions"}
  models_config_path: {Path(__file__).resolve().parents[1] / "config" / "models.default.yaml"}
""",
        encoding="utf-8",
    )
    runtime = AIRuntime(load_runtime_config(config_file))
    with pytest.raises(RetryExhaustedError):
        runtime.run_task("resume_parsing", "should fail")
