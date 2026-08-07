"""Google Calendar CalendarProvider (OAuth2 + FreeBusy + Events/Meet)."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

from app.domains.integrations.provider.calendar_base import (
    BusyPeriod,
    CalendarConnectionResult,
    CalendarEventResult,
    CalendarProvider,
    OAuthTokenBundle,
)

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_FREEBUSY_URL = 'https://www.googleapis.com/calendar/v3/freeBusy'
GOOGLE_EVENTS_URL = 'https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'

SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/userinfo.email',
]


def _client_id() -> str:
    return (os.getenv('GOOGLE_OAUTH_CLIENT_ID') or '').strip()


def _client_secret() -> str:
    return (os.getenv('GOOGLE_OAUTH_CLIENT_SECRET') or '').strip()


def _redirect_uri() -> str:
    return (os.getenv('GOOGLE_OAUTH_REDIRECT_URI') or '').strip()


def google_oauth_configured() -> bool:
    return bool(_client_id() and _client_secret() and _redirect_uri())


def build_google_auth_url(state: str) -> str:
    params = {
        'client_id': _client_id(),
        'redirect_uri': _redirect_uri(),
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'consent',
        'include_granted_scopes': 'true',
        'state': state,
    }
    return f'{GOOGLE_AUTH_URL}?{urlencode(params)}'


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            'code': code,
            'client_id': _client_id(),
            'client_secret': _client_secret(),
            'redirect_uri': _redirect_uri(),
            'grant_type': 'authorization_code',
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_rfc3339(value: str) -> datetime:
    if not value:
        raise ValueError('empty datetime')
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    return datetime.fromisoformat(value)


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


class GoogleCalendarProvider(CalendarProvider):
    provider_type = 'google_calendar'

    def _headers(self, tokens: OAuthTokenBundle) -> dict[str, str]:
        return {
            'Authorization': f'{tokens.token_type or "Bearer"} {tokens.access_token}',
            'Content-Type': 'application/json',
        }

    def refresh_access_token(self, tokens: OAuthTokenBundle) -> OAuthTokenBundle:
        if not tokens.refresh_token:
            raise ValueError('No refresh token available')
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                'client_id': _client_id(),
                'client_secret': _client_secret(),
                'refresh_token': tokens.refresh_token,
                'grant_type': 'refresh_token',
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        expires_in = int(data.get('expires_in') or 3600)
        return OAuthTokenBundle(
            access_token=data['access_token'],
            refresh_token=tokens.refresh_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
            token_type=data.get('token_type') or 'Bearer',
            scope=data.get('scope') or tokens.scope,
            raw=data,
        )

    def get_free_busy(
        self,
        tokens: OAuthTokenBundle,
        time_min: datetime,
        time_max: datetime,
        calendar_id: str = 'primary',
    ) -> list[BusyPeriod]:
        body = {
            'timeMin': _to_rfc3339(time_min),
            'timeMax': _to_rfc3339(time_max),
            'items': [{'id': calendar_id}],
        }
        resp = requests.post(
            GOOGLE_FREEBUSY_URL,
            headers=self._headers(tokens),
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        calendars = data.get('calendars') or {}
        cal = calendars.get(calendar_id) or {}
        busy = []
        for period in cal.get('busy') or []:
            try:
                busy.append(
                    BusyPeriod(
                        start=_parse_rfc3339(period['start']),
                        end=_parse_rfc3339(period['end']),
                    )
                )
            except (KeyError, ValueError) as exc:
                logger.warning('[google_calendar] skip bad busy period: %s', exc)
        return busy

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
        attendees = [{'email': e} for e in attendee_emails if e]
        # Wall-clock local times + explicit timeZone (Google Calendar preference)
        start_local = start.astimezone(ZoneInfo(timezone)) if start.tzinfo else start.replace(tzinfo=ZoneInfo(timezone))
        end_local = end.astimezone(ZoneInfo(timezone)) if end.tzinfo else end.replace(tzinfo=ZoneInfo(timezone))
        body: dict[str, Any] = {
            'summary': summary,
            'description': description or '',
            'start': {
                'dateTime': start_local.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_local.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': timezone,
            },
            'attendees': attendees,
        }
        params: dict[str, Any] = {'sendUpdates': 'all'}
        if create_meet:
            body['conferenceData'] = {
                'createRequest': {
                    'requestId': str(uuid.uuid4()),
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                }
            }
            params['conferenceDataVersion'] = 1

        url = GOOGLE_EVENTS_URL.format(calendar_id=requests.utils.quote(calendar_id, safe=''))
        try:
            resp = requests.post(
                url,
                headers=self._headers(tokens),
                params=params,
                json=body,
                timeout=45,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.exception('[google_calendar] create_event failed')
            return CalendarEventResult(success=False, error=str(exc))

        data = resp.json()
        meet_link = None
        conf = data.get('conferenceData') or {}
        for ep in conf.get('entryPoints') or []:
            if ep.get('entryPointType') == 'video' and ep.get('uri'):
                meet_link = ep['uri']
                break
        if not meet_link:
            meet_link = data.get('hangoutLink')

        return CalendarEventResult(
            success=True,
            event_id=data.get('id'),
            meet_link=meet_link,
            html_link=data.get('htmlLink'),
        )

    def test_connection(self, tokens: OAuthTokenBundle) -> CalendarConnectionResult:
        try:
            resp = requests.get(
                GOOGLE_USERINFO_URL,
                headers=self._headers(tokens),
                timeout=20,
            )
            resp.raise_for_status()
            email = (resp.json() or {}).get('email') or ''
            return CalendarConnectionResult(
                success=True,
                message=f'Connected as {email}' if email else 'Connected',
            )
        except requests.RequestException as exc:
            return CalendarConnectionResult(success=False, error=str(exc))
