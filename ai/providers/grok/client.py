"""HTTP client for the Grok (X.AI) chat completions API."""

from __future__ import annotations

from typing import Any

import httpx

from providers.grok.config import GrokProviderConfig
from providers.grok.exceptions import map_httpx_error, map_http_status


class GrokChatResponse:
    def __init__(self, content: str, model: str, raw: dict[str, Any]) -> None:
        self.content = content
        self.model = model
        self.raw = raw


class GrokClient:
    """OpenAI-compatible client for X.AI Grok."""

    def __init__(
        self,
        config: GrokProviderConfig,
        *,
        provider_id: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._config = config
        self._provider_id = provider_id
        self._owns_client = http_client is None
        self._client = http_client or self._build_client()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def chat_completions(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
        timeout_seconds: float | None = None,
    ) -> GrokChatResponse:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        timeout = timeout_seconds if timeout_seconds is not None else self._config.default_timeout_seconds
        try:
            response = self._client.post(
                "/chat/completions",
                json=body,
                headers=self._headers(),
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise map_http_status(
                exc.response.status_code,
                f"Grok API error ({exc.response.status_code}): {exc.response.text}",
                provider_id=self._provider_id,
            ) from exc
        except Exception as exc:
            raise map_httpx_error(exc, provider_id=self._provider_id) from exc

        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return GrokChatResponse(content=content, model=model, raw=payload)

    def health_probe(self, *, timeout_seconds: float = 10.0) -> bool:
        try:
            self._client.get(
                "/models",
                headers=self._headers(),
                timeout=timeout_seconds,
            ).raise_for_status()
            return True
        except Exception:
            return False

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self._config.base_url,
            timeout=httpx.Timeout(self._config.default_timeout_seconds),
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers
