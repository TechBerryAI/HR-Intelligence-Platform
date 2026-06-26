"""Base provider helpers."""

from __future__ import annotations

from runtime.interfaces.provider import LLMProvider


class BaseProvider(LLMProvider):
    """Shared provider utilities."""

    def __init__(self, provider_id: str, provider_type: str, config: dict) -> None:
        self._provider_id = provider_id
        self._provider_type = provider_type
        self._config = config

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def provider_type(self) -> str:
        return self._provider_type

    @property
    def config(self) -> dict:
        return self._config
