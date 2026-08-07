"""Calendar provider DTOs and ABC — parallel to JobProvider (not job-board)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class BusyPeriod:
    start: datetime
    end: datetime


@dataclass
class CalendarEventResult:
    success: bool
    event_id: str | None = None
    meet_link: str | None = None
    html_link: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CalendarConnectionResult:
    success: bool
    message: str | None = None
    error: str | None = None


@dataclass
class OAuthTokenBundle:
    """Decrypted OAuth tokens for a calendar provider."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    token_type: str = 'Bearer'
    scope: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class CalendarProvider(ABC):
    """Provider-agnostic calendar adapter (Google, future Outlook/Graph)."""

    provider_type: str = ''

    @abstractmethod
    def get_free_busy(
        self,
        tokens: OAuthTokenBundle,
        time_min: datetime,
        time_max: datetime,
        calendar_id: str = 'primary',
    ) -> list[BusyPeriod]:
        ...

    @abstractmethod
    def create_event(
        self,
        tokens: OAuthTokenBundle,
        *,
        summary: str,
        description: str,
        start: datetime,
        end: datetime,
        attendee_emails: list[str],
        timezone: str,
        calendar_id: str = 'primary',
        create_meet: bool = True,
    ) -> CalendarEventResult:
        ...

    @abstractmethod
    def test_connection(self, tokens: OAuthTokenBundle) -> CalendarConnectionResult:
        ...

    @abstractmethod
    def refresh_access_token(self, tokens: OAuthTokenBundle) -> OAuthTokenBundle:
        ...
