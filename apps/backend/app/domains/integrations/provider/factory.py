"""JobProvider factory — builtins + dynamic HTTP providers."""
from __future__ import annotations

from app.domains.integrations.config import PROVIDER_CATALOG, is_builtin
from app.domains.integrations.provider.base import JobProvider
from app.domains.integrations.provider.generic import GenericHttpProvider
from app.domains.integrations.provider.linkedin import LinkedInProvider
from app.domains.integrations.provider.naukri import NaukriProvider

_REGISTRY: dict[str, JobProvider] = {}

_SPECIFIC = {
    'linkedin': LinkedInProvider,
    'naukri': NaukriProvider,
}


def register_provider(provider: JobProvider) -> None:
    key = (provider.provider_type or '').strip().lower()
    if not key:
        raise ValueError('provider_type is required')
    _REGISTRY[key] = provider


def get_provider(provider_type: str) -> JobProvider | None:
    key = (provider_type or '').strip().lower()
    if not key:
        return None
    if key in _REGISTRY:
        return _REGISTRY[key]
    # Dynamic custom HTTP adapter (not pre-registered)
    if not is_builtin(key):
        return GenericHttpProvider(provider_type=key)
    return None


def list_registered_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


def ensure_default_providers() -> None:
    """Register fixed LinkedIn / Naukri adapters only."""
    if _REGISTRY:
        return
    for meta in PROVIDER_CATALOG:
        pid = meta['id']
        adapter = meta.get('adapter') or pid
        cls = _SPECIFIC.get(adapter)
        if cls:
            register_provider(cls())
