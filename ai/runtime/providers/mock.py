"""Mock provider for runtime testing without external AI services."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from runtime.exceptions import ProviderError, ProviderNotAvailableError, ProviderTimeoutError
from runtime.interfaces.types import InferenceRequest, InferenceResponse, ProviderHealth
from runtime.providers.base import BaseProvider


class MockProvider(BaseProvider):
    """Deterministic provider used for tests and local development."""

    def __init__(self, provider_id: str, config: dict[str, Any]) -> None:
        super().__init__(provider_id, "mock", config)
        self._failure_count = 0
        self._last_success_at: datetime | None = None
        self._last_failure_at: datetime | None = None
        self._last_error: str | None = None

    def is_configured(self) -> bool:
        return bool(self._config.get("enabled", True))

    def complete(self, request: InferenceRequest) -> InferenceResponse:
        if not self.is_configured():
            raise ProviderNotAvailableError(
                f"Provider '{self.provider_id}' is not configured",
                provider_id=self.provider_id,
                retryable=False,
            )

        timeout_seconds = request.timeout_seconds or self._config.get("timeout_seconds")
        if timeout_seconds is not None and float(timeout_seconds) <= 0:
            raise ProviderTimeoutError(
                f"Provider '{self.provider_id}' timed out",
                provider_id=self.provider_id,
            )

        fail_until_attempt = int(self._config.get("fail_until_attempt", 0))
        current_attempt = int(request.metadata.get("attempt", 1))
        if current_attempt <= fail_until_attempt:
            self._record_failure("Simulated provider failure")
            raise ProviderError(
                f"Simulated failure on attempt {current_attempt}",
                provider_id=self.provider_id,
                retryable=True,
                status_code=503,
            )

        if self._config.get("always_succeed") is False:
            self._record_failure("Mock provider configured to fail")
            raise ProviderError(
                "Mock provider configured to fail",
                provider_id=self.provider_id,
                retryable=False,
            )

        latency_ms = float(self._config.get("default_latency_ms", 5))
        time.sleep(latency_ms / 1000.0)

        content = self._build_response(request)
        self._record_success()
        return InferenceResponse(
            content=content,
            provider_id=self.provider_id,
            model=request.model,
            latency_ms=latency_ms,
            raw={"mock": True, "task": request.task},
            token_usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )

    def health_check(self) -> ProviderHealth:
        start = time.perf_counter()
        available = self.is_configured()
        latency_ms = (time.perf_counter() - start) * 1000.0
        if available:
            self._record_success()
        else:
            self._record_failure("Provider disabled")
        return ProviderHealth(
            provider_id=self.provider_id,
            available=available,
            latency_ms=latency_ms,
            failure_count=self._failure_count,
            last_success_at=self._last_success_at,
            last_failure_at=self._last_failure_at,
            last_error=self._last_error,
            checked_at=datetime.now(UTC),
        )

    def _build_response(self, request: InferenceRequest) -> str:
        custom = self._config.get("responses", {})
        if request.task in custom:
            payload = custom[request.task]
            if isinstance(payload, str):
                return payload
            return json.dumps(payload)

        payload = {
            "task": request.task,
            "schema_id": request.schema_id,
            "model": request.model,
            "input_preview": request.input_text[:120],
            "status": "mock_success",
        }
        return json.dumps(payload)

    def _record_success(self) -> None:
        self._last_success_at = datetime.now(UTC)
        self._last_error = None

    def _record_failure(self, message: str) -> None:
        self._failure_count += 1
        self._last_failure_at = datetime.now(UTC)
        self._last_error = message
