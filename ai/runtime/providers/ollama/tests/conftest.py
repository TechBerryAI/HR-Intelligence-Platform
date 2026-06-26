"""Shared fixtures for Ollama provider tests."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from runtime.providers.ollama.client import OllamaClient
from runtime.providers.ollama.config import OllamaProviderConfig
from runtime.providers.ollama.provider import OllamaProvider


RESUME_RESPONSE = {
    "type": "resume",
    "person": {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "555-0100",
    },
    "skills": [],
    "experience": [],
    "education": [],
}

JD_RESPONSE = {
    "type": "job_description",
    "title": "Backend Engineer",
    "location": "Remote",
    "skills": [],
    "responsibilities": [],
}


def _chat_response_payload(content: str, *, model: str = "qwen2.5:7b-instruct") -> dict[str, Any]:
    return {
        "model": model,
        "created_at": "2026-01-01T00:00:00Z",
        "message": {"role": "assistant", "content": content},
        "done": True,
        "prompt_eval_count": 42,
        "eval_count": 128,
        "total_duration": 1_500_000_000,
    }


def build_ollama_mock_transport(
    *,
    chat_content: str | dict[str, Any] | None = None,
    models: list[str] | None = None,
    chat_status: int = 200,
    tags_status: int = 200,
) -> httpx.MockTransport:
    """Build a mock transport that simulates Ollama API responses."""
    if models is None:
        models = ["qwen2.5:7b-instruct"]
    if chat_content is None:
        chat_content = RESUME_RESPONSE
    if isinstance(chat_content, dict):
        chat_text = json.dumps(chat_content)
    else:
        chat_text = chat_content

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(
                tags_status,
                json={"models": [{"name": name, "size": 4_000_000_000} for name in models]},
            )
        if request.url.path == "/api/chat":
            if chat_status != 200:
                return httpx.Response(chat_status, text="server error")
            return httpx.Response(200, json=_chat_response_payload(chat_text))
        return httpx.Response(404, text="not found")

    return httpx.MockTransport(handler)


@pytest.fixture
def ollama_config() -> OllamaProviderConfig:
    return OllamaProviderConfig(
        enabled=True,
        base_url="http://ollama.test",
        default_timeout_seconds=30.0,
    )


@pytest.fixture
def ollama_client(ollama_config: OllamaProviderConfig) -> OllamaClient:
    transport = build_ollama_mock_transport()
    http_client = httpx.Client(transport=transport, base_url=ollama_config.base_url)
    client = OllamaClient(ollama_config, provider_id="ollama", http_client=http_client)
    yield client
    client.close()


@pytest.fixture
def ollama_provider() -> OllamaProvider:
    transport = build_ollama_mock_transport()
    http_client = httpx.Client(transport=transport, base_url="http://ollama.test")
    config = {
        "type": "ollama",
        "enabled": True,
        "base_url": "http://ollama.test",
        "default_timeout_seconds": 30.0,
    }
    provider = OllamaProvider("ollama", config)
    provider._client = OllamaClient(
        provider._ollama_config,
        provider_id="ollama",
        http_client=http_client,
    )
    provider._health = provider._health.__class__(provider._client, "ollama")
    yield provider
    provider.close()
