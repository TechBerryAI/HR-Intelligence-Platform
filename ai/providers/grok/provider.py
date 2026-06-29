"""Production Grok (X.AI) LLM provider."""

from __future__ import annotations

import time
from typing import Any

from runtime.exceptions import ProviderNotAvailableError
from runtime.interfaces.types import InferenceRequest, InferenceResponse, ProviderHealth
from providers.base import BaseProvider
from providers.grok.client import GrokClient
from providers.grok.config import GrokProviderConfig
from providers.grok.exceptions import map_httpx_error
from providers.grok.health import GrokHealthChecker
from providers.grok.structured_output import build_messages, normalize_content


class GrokProvider(BaseProvider):
    """Grok-backed LLM provider conforming to the runtime provider interface."""

    def __init__(self, provider_id: str, config: dict[str, Any]) -> None:
        super().__init__(provider_id, "grok", config)
        self._grok_config = GrokProviderConfig.from_dict(config)
        self._client = GrokClient(self._grok_config, provider_id=provider_id)
        self._health = GrokHealthChecker(self._client, provider_id)

    def is_configured(self) -> bool:
        return self._grok_config.enabled and bool(self._grok_config.api_key)

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        if not self.is_configured():
            raise ProviderNotAvailableError(
                f"Provider '{self.provider_id}' is not configured",
                provider_id=self.provider_id,
                retryable=False,
            )

        messages = build_messages(prompt=request.prompt, input_text=request.input_text)
        model = request.model or self._grok_config.model
        timeout_seconds = request.timeout_seconds or self._grok_config.default_timeout_seconds

        start = time.perf_counter()
        try:
            chat_response = self._client.chat_completions(
                model=model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                json_mode=bool(request.schema_id),
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            self._health.record_failure(str(exc))
            if hasattr(exc, "provider_id"):
                raise
            raise map_httpx_error(exc, provider_id=self.provider_id) from exc

        latency_ms = (time.perf_counter() - start) * 1000.0
        content = normalize_content(chat_response.content, schema_id=request.schema_id)
        self._health.record_success()

        return InferenceResponse(
            content=content,
            provider_id=self.provider_id,
            model=model,
            latency_ms=latency_ms,
            raw=chat_response.raw,
        )

    def health_check(self) -> ProviderHealth:
        if not self.is_configured():
            return ProviderHealth(
                provider_id=self.provider_id,
                available=False,
                latency_ms=0.0,
                last_error="API key not configured",
            )
        return self._health.check()
