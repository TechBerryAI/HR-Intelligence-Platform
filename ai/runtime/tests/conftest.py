"""Shared test fixtures for AI runtime."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

import runtime.core.runtime as runtime_module
from runtime.config.loader import DEFAULT_CONFIG_PATH
from runtime.core.runtime import AIRuntime
from providers.ollama.client import OllamaClient
from providers.ollama.provider import OllamaProvider
from providers.ollama.tests.conftest import (
    JD_RESPONSE,
    RESUME_RESPONSE,
    build_ollama_mock_transport,
)


def _mock_ollama_client_factory(chat_content=RESUME_RESPONSE):
    transport = build_ollama_mock_transport(chat_content=chat_content)

    def factory(config, provider_id):
        http_client = httpx.Client(transport=transport, base_url=config.base_url)
        return OllamaClient(config, provider_id=provider_id, http_client=http_client)

    return factory


@pytest.fixture
def runtime() -> AIRuntime:
    runtime_module._default_runtime = None
    with patch(
        "providers.ollama.provider.OllamaClient",
        side_effect=_mock_ollama_client_factory(),
    ):
        yield AIRuntime.from_config_path(DEFAULT_CONFIG_PATH)


@pytest.fixture(autouse=True)
def reset_runtime_singleton() -> None:
    runtime_module._default_runtime = None
    yield
    runtime_module._default_runtime = None
