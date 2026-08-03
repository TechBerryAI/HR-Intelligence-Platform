"""Provider health monitoring."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime

from runtime.interfaces.provider import LLMProvider
from runtime.interfaces.types import ProviderHealth

# Transient chat failures must not disable the only provider mid-bulk-job.
# Mark unavailable only after many consecutive failures; auto-recover after cooldown.
_UNAVAILABLE_AFTER = max(1, int(os.getenv("AI_PROVIDER_UNAVAILABLE_AFTER", "12")))
_COOLDOWN_SECONDS = max(1.0, float(os.getenv("AI_PROVIDER_COOLDOWN_SECONDS", "45")))


class HealthMonitor:
    """Track provider availability, latency, and failure counts."""

    def __init__(self) -> None:
        self._health: dict[str, ProviderHealth] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._unavailable_until: dict[str, float] = {}

    def get(self, provider_id: str) -> ProviderHealth | None:
        health = self._health.get(provider_id)
        if health is None:
            return None
        # Auto-recover after cooldown so long bulk jobs keep using Ollama
        until = self._unavailable_until.get(provider_id, 0.0)
        if not health.available and time.monotonic() >= until:
            recovered = ProviderHealth(
                provider_id=provider_id,
                available=True,
                latency_ms=health.latency_ms,
                failure_count=health.failure_count,
                last_success_at=health.last_success_at,
                last_failure_at=health.last_failure_at,
                last_error=health.last_error,
                checked_at=datetime.now(UTC),
            )
            self._health[provider_id] = recovered
            self._consecutive_failures[provider_id] = 0
            self._unavailable_until.pop(provider_id, None)
            return recovered
        return health

    def all(self) -> list[ProviderHealth]:
        return sorted(
            [self.get(pid) or h for pid, h in self._health.items()],
            key=lambda item: item.provider_id,
        )

    def refresh(self, provider: LLMProvider) -> ProviderHealth:
        health = provider.health_check()
        self._health[provider.provider_id] = health
        if health.available:
            self._consecutive_failures[provider.provider_id] = 0
            self._unavailable_until.pop(provider.provider_id, None)
        return health

    def refresh_all(self, providers: dict[str, LLMProvider]) -> list[ProviderHealth]:
        return [self.refresh(provider) for provider in providers.values()]

    def record_success(self, provider_id: str, *, latency_ms: float | None = None) -> None:
        current = self._health.get(provider_id)
        self._consecutive_failures[provider_id] = 0
        self._unavailable_until.pop(provider_id, None)
        self._health[provider_id] = ProviderHealth(
            provider_id=provider_id,
            available=True,
            latency_ms=latency_ms if latency_ms is not None else (current.latency_ms if current else None),
            failure_count=current.failure_count if current else 0,
            last_success_at=datetime.now(UTC),
            last_failure_at=current.last_failure_at if current else None,
            last_error=None,
            checked_at=datetime.now(UTC),
        )

    def record_failure(self, provider_id: str, error: str) -> None:
        current = self._health.get(provider_id)
        failure_count = (current.failure_count if current else 0) + 1
        consecutive = self._consecutive_failures.get(provider_id, 0) + 1
        self._consecutive_failures[provider_id] = consecutive
        # Keep provider available through transient timeouts; only trip after a streak
        available = consecutive < _UNAVAILABLE_AFTER
        if not available:
            self._unavailable_until[provider_id] = time.monotonic() + _COOLDOWN_SECONDS
        self._health[provider_id] = ProviderHealth(
            provider_id=provider_id,
            available=available,
            latency_ms=current.latency_ms if current else None,
            failure_count=failure_count,
            last_success_at=current.last_success_at if current else None,
            last_failure_at=datetime.now(UTC),
            last_error=error,
            checked_at=datetime.now(UTC),
        )
