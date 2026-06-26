"""HTTP client for the Ollama API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from runtime.providers.ollama.config import OllamaProviderConfig
from runtime.providers.ollama.exceptions import map_httpx_error, map_http_status
from runtime.providers.ollama.models import OllamaChatResponse, OllamaModelInfo, OllamaStreamChunk


class OllamaClient:
    """Connection-managed Ollama HTTP client."""

    def __init__(
        self,
        config: OllamaProviderConfig,
        *,
        provider_id: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._provider_id = provider_id
        self._owns_client = http_client is None
        self._client = http_client or self._build_client()

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def list_models(self) -> list[OllamaModelInfo]:
        """Discover models available on the Ollama host."""
        response = self._request("GET", "/api/tags")
        payload = response.json()
        models = payload.get("models") or []
        return [OllamaModelInfo.from_api(item) for item in models if isinstance(item, dict)]

    def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: str | dict[str, Any] | None = None,
        stream: bool = False,
        timeout_seconds: float | None = None,
    ) -> OllamaChatResponse:
        """Execute a non-streaming chat completion."""
        if stream:
            chunks = list(
                self.chat_stream(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    timeout_seconds=timeout_seconds,
                )
            )
            content = "".join(chunk.content for chunk in chunks)
            last = chunks[-1] if chunks else None
            return OllamaChatResponse(
                content=content,
                model=model,
                done=True,
                raw=last.raw if last else {},
            )

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if response_format is not None:
            body["format"] = response_format

        response = self._request(
            "POST",
            "/api/chat",
            json=body,
            timeout_seconds=timeout_seconds,
        )
        return OllamaChatResponse.from_api(response.json())

    def chat_stream(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: str | dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> Iterator[OllamaStreamChunk]:
        """Stream chat completion chunks (streaming-ready architecture)."""
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if response_format is not None:
            body["format"] = response_format

        timeout = self._resolve_timeout(timeout_seconds)
        try:
            with self._client.stream(
                "POST",
                "/api/chat",
                json=body,
                headers=self._headers(),
                timeout=timeout,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    payload = json.loads(line)
                    yield OllamaStreamChunk.from_api(payload)
        except Exception as exc:
            raise map_httpx_error(exc, provider_id=self._provider_id) from exc

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._config.base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(self._config.default_timeout_seconds),
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers

    def _resolve_timeout(self, timeout_seconds: float | None) -> httpx.Timeout:
        seconds = timeout_seconds if timeout_seconds is not None else self._config.default_timeout_seconds
        return httpx.Timeout(seconds)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout_seconds: float | None = None,
    ) -> httpx.Response:
        timeout = self._resolve_timeout(timeout_seconds)
        try:
            response = self._client.request(
                method,
                path,
                json=json,
                headers=self._headers(),
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            raise map_http_status(
                exc.response.status_code,
                f"Ollama API error ({exc.response.status_code}): {exc.response.text}",
                provider_id=self._provider_id,
            ) from exc
        except Exception as exc:
            raise map_httpx_error(exc, provider_id=self._provider_id) from exc
