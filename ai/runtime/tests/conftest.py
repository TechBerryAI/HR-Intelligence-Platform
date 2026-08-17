"""Shared test fixtures for AI runtime."""

from __future__ import annotations

import os
from unittest.mock import patch

import httpx
import pytest

from runtime.config.loader import DEFAULT_CONFIG_PATH
from runtime.core.runtime import AIRuntime, reset_runtime
from providers.ollama.client import OllamaClient
from providers.ollama.tests.conftest import (
    RESUME_RESPONSE,
    build_ollama_mock_transport,
)


def _mock_ollama_client_factory(chat_content=RESUME_RESPONSE):
    transport = build_ollama_mock_transport(chat_content=chat_content)

    def factory(config, provider_id):
        http_client = httpx.Client(transport=transport, base_url=config.base_url)
        return OllamaClient(config, provider_id=provider_id, http_client=http_client)

    return factory


@pytest.fixture(autouse=True)
def _ensure_ollama_model(monkeypatch: pytest.MonkeyPatch) -> None:
    if not (os.getenv("OLLAMA_MODEL") or "").strip():
        monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")


@pytest.fixture
def runtime() -> AIRuntime:
    reset_runtime()
    with patch(
        "providers.ollama.provider.OllamaClient",
        side_effect=_mock_ollama_client_factory(),
    ):
        yield AIRuntime.from_config_path(DEFAULT_CONFIG_PATH)
    reset_runtime()


@pytest.fixture(autouse=True)
def reset_runtime_singleton() -> None:
    reset_runtime()
    yield
    reset_runtime()
