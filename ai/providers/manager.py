"""Provider selection and fallback chain."""

from __future__ import annotations

from runtime.config.models import RuntimeConfig, TaskDefinition
from runtime.exceptions import ConfigurationError, ProviderNotAvailableError
from runtime.health.monitor import HealthMonitor
from runtime.interfaces.provider import LLMProvider
from providers.factory import ProviderFactory


class ProviderManager:
    """Configuration-driven provider selection."""

    def __init__(self, config: RuntimeConfig, health_monitor: HealthMonitor) -> None:
        self._config = config
        self._health = health_monitor
        self._providers: dict[str, LLMProvider] = {}
        self._load_providers()

    @property
    def providers(self) -> dict[str, LLMProvider]:
        return dict(self._providers)

    def get(self, provider_id: str) -> LLMProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise ConfigurationError(f"Provider not configured: {provider_id}")
        return provider

    def get_provider_chain(self, task: TaskDefinition) -> list[LLMProvider]:
        """Build ordered provider chain for a task (preferred → primary → fallbacks)."""
        ordered_ids: list[str] = []
        if task.preferred_provider:
            ordered_ids.append(task.preferred_provider)
        if self._config.routing.primary not in ordered_ids:
            ordered_ids.append(self._config.routing.primary)
        for provider_id in self._config.routing.fallback_chain:
            if provider_id not in ordered_ids:
                ordered_ids.append(provider_id)

        chain: list[LLMProvider] = []
        for provider_id in ordered_ids:
            provider = self.get(provider_id)
            health = self._health.get(provider_id)
            if health is not None and not health.available:
                continue
            if not provider.is_configured():
                continue
            chain.append(provider)

        if not chain:
            raise ProviderNotAvailableError("No healthy configured providers available")
        return chain

    def list_provider_ids(self) -> list[str]:
        return sorted(self._providers.keys())

    def _load_providers(self) -> None:
        loaded: dict[str, LLMProvider] = {}
        for provider_id, provider_config in self._config.providers.items():
            loaded[provider_id] = ProviderFactory.create(provider_id, provider_config)
        self._providers = loaded

        required = {self._config.routing.primary, *self._config.routing.fallback_chain}
        missing = sorted(required - set(self._providers))
        if missing:
            raise ConfigurationError(f"Routing references undefined providers: {missing}")
