"""Typed exceptions for the AI runtime."""

from __future__ import annotations


class RuntimeError(Exception):
    """Base exception for AI runtime failures."""


class ConfigurationError(RuntimeError):
    """Invalid or missing runtime configuration."""


class RegistryError(RuntimeError):
    """Registry lookup or load failure."""


class TaskNotFoundError(RegistryError):
    """Requested task is not registered."""


class SchemaNotFoundError(RegistryError):
    """Requested schema is not registered."""


class ProviderError(RuntimeError):
    """Provider execution failure."""

    def __init__(
        self,
        message: str,
        *,
        provider_id: str | None = None,
        retryable: bool = True,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_id = provider_id
        self.retryable = retryable
        self.status_code = status_code


class ProviderNotAvailableError(ProviderError):
    """Provider is unhealthy or not configured."""


class ProviderTimeoutError(ProviderError):
    """Provider request exceeded timeout."""


class ValidationError(RuntimeError):
    """Structured output failed validation."""

    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class RetryExhaustedError(RuntimeError):
    """All retry attempts and fallbacks exhausted."""

    def __init__(self, message: str, *, attempts: int = 0) -> None:
        super().__init__(message)
        self.attempts = attempts
