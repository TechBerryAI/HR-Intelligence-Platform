"""Provider factory."""

from __future__ import annotations

from typing import Any

from runtime.exceptions import ConfigurationError
from runtime.interfaces.provider import LLMProvider
from providers.mock import MockProvider
from providers.ollama import OllamaProvider

_PROVIDER_TYPES: dict[str, type[LLMProvider]] = {
    "mock": MockProvider,
    "ollama": OllamaProvider,
}


class ProviderFactory:
    """Instantiate providers from configuration."""

    @classmethod
    def register_provider_type(cls, provider_type: str, implementation: type[LLMProvider]) -> None:
        _PROVIDER_TYPES[provider_type] = implementation

    @classmethod
    def create(cls, provider_id: str, config: dict[str, Any]) -> LLMProvider:
        provider_type = config.get("type")
        if not provider_type:
            raise ConfigurationError(f"Provider '{provider_id}' missing type")
        implementation = _PROVIDER_TYPES.get(provider_type)
        if implementation is None:
            raise ConfigurationError(
                f"Unsupported provider type '{provider_type}' for '{provider_id}'. "
                "Register an implementation via ProviderFactory.register_provider_type()."
            )
        return implementation(provider_id, config)

    @classmethod
    def supported_types(cls) -> list[str]:
        return sorted(_PROVIDER_TYPES.keys())
