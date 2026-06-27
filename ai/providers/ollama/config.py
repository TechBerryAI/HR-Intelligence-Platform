"""Ollama provider configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OllamaProviderConfig:
    """Validated configuration for the Ollama provider."""

    enabled: bool = True
    base_url: str = "http://localhost:11434"
    default_timeout_seconds: float = 120.0
    api_key: str | None = None
    stream: bool = False

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> OllamaProviderConfig:
        base_url = str(config.get("base_url") or config.get("host") or "http://localhost:11434")
        base_url = base_url.rstrip("/")
        timeout = config.get("default_timeout_seconds") or config.get("timeout_seconds") or 120.0
        return cls(
            enabled=bool(config.get("enabled", True)),
            base_url=base_url,
            default_timeout_seconds=float(timeout),
            api_key=config.get("api_key") or None,
            stream=bool(config.get("stream", False)),
        )
