"""Provider factory."""

from __future__ import annotations

import importlib
from typing import Any

from runtime.exceptions import ConfigurationError
from runtime.interfaces.provider import LLMProvider
from providers.mock import MockProvider
from providers.ollama import OllamaProvider

_PROVIDER_TYPES: dict[str, type[LLMProvider]] = {
    "mock": MockProvider,
    "ollama": OllamaProvider,
}

_LAZY_PROVIDER_TYPES: dict[str, str] = {
    "grok": "providers.grok.provider.GrokProvider",
}


class ProviderFactory:
    """Instantiate providers from configuration."""

    @classmethod
    def register_provider_type(cls, provider_type: str, implementation: type[LLMProvider]) -> None:
        _PROVIDER_TYPES[provider_type] = implementation

    @classmethod
    def _resolve_implementation(cls, provider_type: str) -> type[LLMProvider] | None:
        implementation = _PROVIDER_TYPES.get(provider_type)
        if implementation is not None:
            return implementation
        lazy_path = _LAZY_PROVIDER_TYPES.get(provider_type)
        if lazy_path is None:
            return None
        module_name, class_name = lazy_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        implementation = getattr(module, class_name)
        _PROVIDER_TYPES[provider_type] = implementation
        return implementation

    @classmethod
    def create(cls, provider_id: str, config: dict[str, Any]) -> LLMProvider:
        provider_type = config.get("type")
        if not provider_type:
            raise ConfigurationError(f"Provider '{provider_id}' missing type")
        implementation = cls._resolve_implementation(provider_type)
        if implementation is None:
            raise ConfigurationError(
                f"Unsupported provider type '{provider_type}' for '{provider_id}'. "
                "Register an implementation via ProviderFactory.register_provider_type()."
            )
        return implementation(provider_id, config)

    @classmethod
    def supported_types(cls) -> list[str]:
        return sorted({*_PROVIDER_TYPES.keys(), *_LAZY_PROVIDER_TYPES.keys()})
