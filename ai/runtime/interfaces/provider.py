"""LLM provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from runtime.interfaces.types import InferenceRequest, InferenceResponse, ProviderHealth


class LLMProvider(ABC):
    """Contract every AI provider must implement."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier (e.g. ollama, mock)."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Provider implementation type."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when provider has required configuration."""

    @abstractmethod
    def complete(self, request: InferenceRequest) -> InferenceResponse:
        """Execute inference and return structured response."""

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Probe provider availability and latency."""
