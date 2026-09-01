"""Ollama provider configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OllamaProviderConfig:
    """Validated configuration for the Ollama provider."""

    enabled: bool = True
    base_url: str = "http://192.168.1.200:11434"
    default_timeout_seconds: float = 120.0
    api_key: str | None = None
    stream: bool = False
    # Official Ollama TTL after each request. Avoids repeating ~20s CPU model loads
    # between sequential parses without pinning the model forever (-1).
    keep_alive: str | int = "10m"

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> OllamaProviderConfig:
        base_url = str(config.get("base_url") or config.get("host") or "http://192.168.1.200:11434")
        base_url = base_url.rstrip("/")
        timeout = config.get("default_timeout_seconds") or config.get("timeout_seconds") or 120.0
        keep_alive = config.get("keep_alive", "10m")
        if keep_alive is None or keep_alive == "":
            keep_alive = "10m"
        return cls(
            enabled=bool(config.get("enabled", True)),
            base_url=base_url,
            default_timeout_seconds=float(timeout),
            api_key=config.get("api_key") or None,
            stream=bool(config.get("stream", False)),
            keep_alive=keep_alive if isinstance(keep_alive, (str, int)) else "10m",
        )
