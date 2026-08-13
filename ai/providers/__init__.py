"""Provider implementations.

Imports are lazy so `import providers.ollama.*` does not cycle through
`runtime.core.executor` → `providers.manager` while `providers.base` is
still initializing.
"""

from __future__ import annotations

__all__ = [
    "BaseProvider",
    "MockProvider",
    "OllamaProvider",
    "ProviderFactory",
    "ProviderManager",
]


def __getattr__(name: str):
    if name == "BaseProvider":
        from providers.base import BaseProvider

        return BaseProvider
    if name == "MockProvider":
        from providers.mock import MockProvider

        return MockProvider
    if name == "OllamaProvider":
        from providers.ollama import OllamaProvider

        return OllamaProvider
    if name == "ProviderFactory":
        from providers.factory import ProviderFactory

        return ProviderFactory
    if name == "ProviderManager":
        from providers.manager import ProviderManager

        return ProviderManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
