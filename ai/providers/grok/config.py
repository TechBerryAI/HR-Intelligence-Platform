"""Grok provider configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


def _resolve_api_key(config: dict[str, Any]) -> str | None:
    explicit = config.get("api_key")
    if explicit:
        return str(explicit)
    for env_name in ("XAI_API_KEY", "HRMS_API_KEY_1", "HRMS_API_KEY_2", "HRMS_API_KEY_3", "HRMS_API_KEY_4"):
        value = os.getenv(env_name)
        if value:
            return value
    return None


@dataclass(frozen=True)
class GrokProviderConfig:
    """Validated configuration for the Grok (X.AI) provider."""

    enabled: bool = True
    base_url: str = "https://api.x.ai/v1"
    model: str = "grok-4-fast-reasoning"
    api_key: str | None = None
    default_timeout_seconds: float = 45.0

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> GrokProviderConfig:
        base_url = str(config.get("base_url") or os.getenv("XAI_BASE_URL") or "https://api.x.ai/v1")
        base_url = base_url.rstrip("/")
        model = str(config.get("model") or os.getenv("XAI_MODEL") or "grok-4-fast-reasoning")
        timeout = config.get("default_timeout_seconds") or config.get("timeout_seconds") or 45.0
        return cls(
            enabled=bool(config.get("enabled", True)),
            base_url=base_url,
            model=model,
            api_key=_resolve_api_key(config),
            default_timeout_seconds=float(timeout),
        )
