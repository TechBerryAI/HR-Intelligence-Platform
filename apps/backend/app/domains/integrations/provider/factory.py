"""JobProvider factory — register new providers here only."""
from __future__ import annotations

from app.domains.integrations.provider.base import JobProvider
from app.domains.integrations.provider.indeed import IndeedProvider
from app.domains.integrations.provider.linkedin import LinkedInProvider
from app.domains.integrations.provider.naukri import NaukriProvider

_REGISTRY: dict[str, JobProvider] = {}


def register_provider(provider: JobProvider) -> None:
    key = (provider.provider_type or '').strip().lower()
    if not key:
        raise ValueError('provider_type is required')
    _REGISTRY[key] = provider


def get_provider(provider_type: str) -> JobProvider | None:
    return _REGISTRY.get((provider_type or '').strip().lower())


def list_registered_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def ensure_default_providers() -> None:
    """Idempotent registration of built-in mock providers."""
    if _REGISTRY:
        return
    register_provider(LinkedInProvider())
    register_provider(NaukriProvider())
    register_provider(IndeedProvider())
