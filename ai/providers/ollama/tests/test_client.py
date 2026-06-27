"""Ollama HTTP client tests."""

from __future__ import annotations

import json

import httpx
import pytest

from runtime.exceptions import ProviderError, ProviderNotAvailableError, ProviderTimeoutError
from providers.ollama.client import OllamaClient
from providers.ollama.config import OllamaProviderConfig
from providers.ollama.tests.conftest import JD_RESPONSE, RESUME_RESPONSE, build_ollama_mock_transport


def test_list_models(ollama_client: OllamaClient) -> None:
    models = ollama_client.list_models()
    assert len(models) == 1
    assert models[0].name == "qwen2.5:7b-instruct"


def test_chat_completion() -> None:
    transport = build_ollama_mock_transport(chat_content=RESUME_RESPONSE)
    config = OllamaProviderConfig(base_url="http://ollama.test")
    http_client = httpx.Client(transport=transport, base_url=config.base_url)
    client = OllamaClient(config, provider_id="ollama", http_client=http_client)
    try:
        response = client.chat(
            model="qwen2.5:7b-instruct",
            messages=[{"role": "user", "content": "parse"}],
            temperature=0.1,
            max_tokens=1024,
            response_format="json",
        )
        assert json.loads(response.content)["type"] == "resume"
        assert response.token_usage is not None
        assert response.token_usage["total_tokens"] == 170
    finally:
        client.close()


def test_chat_stream() -> None:
    transport = build_ollama_mock_transport(chat_content=JD_RESPONSE)

    def streaming_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/chat":
            lines = [
                json.dumps(
                    {
                        "message": {"content": '{"type":'},
                        "done": False,
                    }
                ),
                json.dumps(
                    {
                        "message": {"content": '"job_description"}'},
                        "done": True,
                    }
                ),
            ]
            return httpx.Response(200, content="\n".join(lines).encode())
        return httpx.Response(404)

    transport = httpx.MockTransport(streaming_handler)
    config = OllamaProviderConfig(base_url="http://ollama.test")
    http_client = httpx.Client(transport=transport, base_url=config.base_url)
    client = OllamaClient(config, provider_id="ollama", http_client=http_client)
    try:
        chunks = list(
            client.chat_stream(
                model="qwen2.5:7b-instruct",
                messages=[{"role": "user", "content": "parse jd"}],
                temperature=0.1,
                max_tokens=512,
            )
        )
        assert len(chunks) == 2
        assert chunks[-1].done is True
    finally:
        client.close()


def test_connection_error_maps_to_not_available() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(handler)
    config = OllamaProviderConfig(base_url="http://ollama.test")
    http_client = httpx.Client(transport=transport, base_url=config.base_url)
    client = OllamaClient(config, provider_id="ollama", http_client=http_client)
    try:
        with pytest.raises(ProviderNotAvailableError):
            client.list_models()
    finally:
        client.close()


def test_http_503_maps_to_retryable_error() -> None:
    transport = build_ollama_mock_transport(chat_status=503)
    config = OllamaProviderConfig(base_url="http://ollama.test")
    http_client = httpx.Client(transport=transport, base_url=config.base_url)
    client = OllamaClient(config, provider_id="ollama", http_client=http_client)
    try:
        with pytest.raises(ProviderError) as exc_info:
            client.chat(
                model="qwen2.5:7b-instruct",
                messages=[{"role": "user", "content": "test"}],
                temperature=0.1,
                max_tokens=128,
            )
        assert exc_info.value.retryable is True
        assert exc_info.value.status_code == 503
    finally:
        client.close()


def test_timeout_maps_to_provider_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    transport = httpx.MockTransport(handler)
    config = OllamaProviderConfig(base_url="http://ollama.test", default_timeout_seconds=1.0)
    http_client = httpx.Client(transport=transport, base_url=config.base_url)
    client = OllamaClient(config, provider_id="ollama", http_client=http_client)
    try:
        with pytest.raises(ProviderTimeoutError):
            client.list_models()
    finally:
        client.close()
