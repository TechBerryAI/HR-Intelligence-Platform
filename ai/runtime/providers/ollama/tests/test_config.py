"""Ollama provider configuration tests."""

from __future__ import annotations

from runtime.providers.ollama.config import OllamaProviderConfig


def test_from_dict_defaults() -> None:
    config = OllamaProviderConfig.from_dict({"type": "ollama"})
    assert config.enabled is True
    assert config.base_url == "http://localhost:11434"
    assert config.default_timeout_seconds == 120.0
    assert config.stream is False


def test_from_dict_custom_values() -> None:
    config = OllamaProviderConfig.from_dict(
        {
            "enabled": False,
            "host": "http://gpu-node:11434/",
            "timeout_seconds": 90,
            "api_key": "secret",
            "stream": True,
        }
    )
    assert config.enabled is False
    assert config.base_url == "http://gpu-node:11434"
    assert config.default_timeout_seconds == 90.0
    assert config.api_key == "secret"
    assert config.stream is True
