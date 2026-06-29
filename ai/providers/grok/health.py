"""Grok health probing and state tracking."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from runtime.interfaces.types import ProviderHealth
from providers.grok.client import GrokClient
from providers.grok.exceptions import map_httpx_error


class GrokHealthChecker:
    def __init__(self, client: GrokClient, provider_id: str) -> None:
        self._client = client
        self._provider_id = provider_id
        self._failure_count = 0
        self._last_success_at: datetime | None = None
        self._last_failure_at: datetime | None = None
        self._last_error: str | None = None

    def check(self) -> ProviderHealth:
        start = time.perf_counter()
        try:
            available = self._client.health_probe()
            latency_ms = (time.perf_counter() - start) * 1000.0
            if available:
                self._record_success()
            else:
                self._record_failure("Grok health probe failed")
            return ProviderHealth(
                provider_id=self._provider_id,
                available=available,
                latency_ms=latency_ms,
                failure_count=self._failure_count,
                last_success_at=self._last_success_at,
                last_failure_at=self._last_failure_at,
                last_error=self._last_error,
                checked_at=datetime.now(UTC),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            mapped = map_httpx_error(exc, provider_id=self._provider_id)
            self._record_failure(str(mapped))
            return ProviderHealth(
                provider_id=self._provider_id,
                available=False,
                latency_ms=latency_ms,
                failure_count=self._failure_count,
                last_success_at=self._last_success_at,
                last_failure_at=self._last_failure_at,
                last_error=self._last_error,
                checked_at=datetime.now(UTC),
            )

    def record_success(self) -> None:
        self._record_success()

    def record_failure(self, message: str) -> None:
        self._record_failure(message)

    def _record_success(self) -> None:
        self._last_success_at = datetime.now(UTC)
        self._last_error = None

    def _record_failure(self, message: str) -> None:
        self._failure_count += 1
        self._last_failure_at = datetime.now(UTC)
        self._last_error = message
