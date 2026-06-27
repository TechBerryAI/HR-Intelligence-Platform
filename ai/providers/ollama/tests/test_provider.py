"""Ollama provider unit tests."""

from __future__ import annotations

import json

import httpx
import pytest

from runtime.exceptions import ProviderNotAvailableError
from runtime.interfaces.types import InferenceRequest
from providers.ollama.client import OllamaClient
from providers.ollama.provider import OllamaProvider
from providers.ollama.tests.conftest import RESUME_RESPONSE, build_ollama_mock_transport


def test_is_configured(ollama_provider: OllamaProvider) -> None:
    assert ollama_provider.is_configured() is True


def test_is_not_configured_when_disabled() -> None:
    provider = OllamaProvider("ollama", {"enabled": False, "base_url": "http://localhost:11434"})
    assert provider.is_configured() is False


def test_complete_returns_inference_response(ollama_provider: OllamaProvider) -> None:
    response = ollama_provider.complete(
        InferenceRequest(
            task="resume_parsing",
            prompt="Parse the resume.",
            input_text="Jane Doe, jane@example.com",
            model="qwen2.5:7b-instruct",
            schema_id="resume_v1",
            temperature=0.1,
            max_tokens=2048,
        )
    )
    payload = json.loads(response.content)
    assert response.provider_id == "ollama"
    assert response.model == "qwen2.5:7b-instruct"
    assert payload["type"] == "resume"
    assert response.latency_ms >= 0
    assert response.token_usage is not None


def test_complete_raises_when_not_configured() -> None:
    provider = OllamaProvider("ollama", {"enabled": False})
    with pytest.raises(ProviderNotAvailableError):
        provider.complete(
            InferenceRequest(
                task="resume_parsing",
                prompt="parse",
                input_text="data",
                model="qwen2.5:7b-instruct",
            )
        )


def test_health_check(ollama_provider: OllamaProvider) -> None:
    health = ollama_provider.health_check()
    assert health.provider_id == "ollama"
    assert health.available is True
    assert health.latency_ms is not None


def test_discover_models(ollama_provider: OllamaProvider) -> None:
    models = ollama_provider.discover_models()
    assert "qwen2.5:7b-instruct" in models


def test_metadata(ollama_provider: OllamaProvider) -> None:
    meta = ollama_provider.metadata()
    assert meta.provider_type == "ollama"
    assert meta.configured is True
    assert "qwen2.5:7b-instruct" in meta.available_models


def test_unconfigured_provider_metadata() -> None:
    provider = OllamaProvider("ollama", {"enabled": False})
    meta = provider.metadata()
    assert meta.configured is False
    assert meta.available_models == ()


def test_health_check_unavailable() -> None:
    transport = build_ollama_mock_transport(tags_status=503)
    http_client = httpx.Client(transport=transport, base_url="http://ollama.test")
    provider = OllamaProvider(
        "ollama",
        {"enabled": True, "base_url": "http://ollama.test"},
    )
    provider._client = OllamaClient(
        provider._ollama_config,
        provider_id="ollama",
        http_client=http_client,
    )
    provider._health = provider._health.__class__(provider._client, "ollama")
    try:
        health = provider.health_check()
        assert health.available is False
        assert health.last_error is not None
    finally:
        provider.close()
