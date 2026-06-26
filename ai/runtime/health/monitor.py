"""Provider health monitoring."""

from __future__ import annotations

from datetime import UTC, datetime

from runtime.interfaces.provider import LLMProvider
from runtime.interfaces.types import ProviderHealth


class HealthMonitor:
    """Track provider availability, latency, and failure counts."""

    def __init__(self) -> None:
        self._health: dict[str, ProviderHealth] = {}

    def get(self, provider_id: str) -> ProviderHealth | None:
        return self._health.get(provider_id)

    def all(self) -> list[ProviderHealth]:
        return sorted(self._health.values(), key=lambda item: item.provider_id)

    def refresh(self, provider: LLMProvider) -> ProviderHealth:
        health = provider.health_check()
        self._health[provider.provider_id] = health
        return health

    def refresh_all(self, providers: dict[str, LLMProvider]) -> list[ProviderHealth]:
        return [self.refresh(provider) for provider in providers.values()]

    def record_success(self, provider_id: str, *, latency_ms: float | None = None) -> None:
        current = self._health.get(provider_id)
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
        self._health[provider_id] = ProviderHealth(
            provider_id=provider_id,
            available=False,
            latency_ms=current.latency_ms if current else None,
            failure_count=failure_count,
            last_success_at=current.last_success_at if current else None,
            last_failure_at=datetime.now(UTC),
            last_error=error,
            checked_at=datetime.now(UTC),
        )
