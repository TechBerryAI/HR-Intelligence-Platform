"""Calendar provider registry (parallel to job provider factory)."""
from __future__ import annotations

from app.domains.integrations.provider.calendar_base import CalendarProvider

_REGISTRY: dict[str, CalendarProvider] = {}
_defaults_loaded = False


def register_calendar_provider(provider: CalendarProvider) -> None:
    key = (provider.provider_type or '').strip().lower()
    if not key:
        raise ValueError('provider_type required')
    _REGISTRY[key] = provider


def get_calendar_provider(provider_type: str = 'google_calendar') -> CalendarProvider | None:
    ensure_default_calendar_providers()
    return _REGISTRY.get((provider_type or '').strip().lower())


def ensure_default_calendar_providers() -> None:
    global _defaults_loaded
    if _defaults_loaded:
        return
    from app.domains.integrations.provider.google_calendar import GoogleCalendarProvider

    register_calendar_provider(GoogleCalendarProvider())
    _defaults_loaded = True
