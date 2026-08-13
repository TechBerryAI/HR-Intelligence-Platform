"""Production Ollama LLM provider."""

from __future__ import annotations

import time
from typing import Any

from runtime.exceptions import ProviderNotAvailableError
from runtime.interfaces.types import InferenceRequest, InferenceResponse, ProviderHealth
from providers.base import BaseProvider
from providers.ollama.client import OllamaClient
from providers.ollama.config import OllamaProviderConfig
from providers.ollama.exceptions import map_httpx_error
from providers.ollama.health import OllamaHealthChecker
from providers.ollama.models import ProviderMetadata
from providers.ollama.structured_output import (
    build_messages,
    normalize_content,
    resolve_response_format,
)


class OllamaProvider(BaseProvider):
    """Ollama-backed LLM provider conforming to the runtime provider interface."""

    def __init__(self, provider_id: str, config: dict[str, Any]) -> None:
        super().__init__(provider_id, "ollama", config)
        self._ollama_config = OllamaProviderConfig.from_dict(config)
        self._client = OllamaClient(self._ollama_config, provider_id=provider_id)
        self._health = OllamaHealthChecker(self._client, provider_id)

    def is_configured(self) -> bool:
        return self._ollama_config.enabled and bool(self._ollama_config.base_url)

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        if not self.is_configured():
            raise ProviderNotAvailableError(
                f"Provider '{self.provider_id}' is not configured",
                provider_id=self.provider_id,
                retryable=False,
            )

        messages = build_messages(prompt=request.prompt, input_text=request.input_text)
        schema_doc = request.metadata.get("json_schema") if request.metadata else None
        if not isinstance(schema_doc, dict):
            schema_doc = None
        response_format = resolve_response_format(request.schema_id, schema_doc)
        timeout_seconds = request.timeout_seconds or self._ollama_config.default_timeout_seconds
        use_stream = bool(self._ollama_config.stream)

        start = time.perf_counter()
        try:
            chat_response = self._client.chat(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format=response_format,
                stream=use_stream,
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
            model=request.model,
            latency_ms=latency_ms,
            raw=chat_response.raw,
            token_usage=chat_response.token_usage,
        )

    def health_check(self) -> ProviderHealth:
        return self._health.check()

    def discover_models(self) -> list[str]:
        """Return model names available on the configured Ollama host."""
        return [model.name for model in self._client.list_models()]

    def metadata(self) -> ProviderMetadata:
        """Expose provider metadata without leaking Ollama specifics to callers."""
        available_models: tuple[str, ...] = ()
        if self.is_configured():
            try:
                available_models = tuple(self.discover_models())
            except Exception:
                available_models = ()
        return ProviderMetadata(
            provider_id=self.provider_id,
            provider_type=self.provider_type,
            base_url=self._ollama_config.base_url,
            configured=self.is_configured(),
            available_models=available_models,
            supports_streaming=True,
            supports_structured_output=True,
        )

    def close(self) -> None:
        self._client.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
