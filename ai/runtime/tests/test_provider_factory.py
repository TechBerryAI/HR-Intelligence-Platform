"""Provider factory tests."""

from __future__ import annotations

import pytest

from runtime.exceptions import ConfigurationError
from runtime.providers.factory import ProviderFactory
from runtime.providers.mock import MockProvider
from runtime.providers.ollama import OllamaProvider


def test_factory_creates_mock_provider() -> None:
    provider = ProviderFactory.create("mock", {"type": "mock", "enabled": True})
    assert isinstance(provider, MockProvider)
    assert provider.provider_id == "mock"


def test_factory_creates_ollama_provider() -> None:
    provider = ProviderFactory.create(
        "ollama",
        {"type": "ollama", "enabled": True, "base_url": "http://localhost:11434"},
    )
    assert isinstance(provider, OllamaProvider)
    assert provider.provider_id == "ollama"


def test_factory_unknown_type() -> None:
    with pytest.raises(ConfigurationError):
        ProviderFactory.create("grok", {"type": "grok"})


def test_register_custom_provider_type() -> None:
    class DummyProvider(MockProvider):
        pass

    ProviderFactory.register_provider_type("dummy", DummyProvider)
    provider = ProviderFactory.create("dummy", {"type": "dummy", "enabled": True})
    assert isinstance(provider, DummyProvider)
