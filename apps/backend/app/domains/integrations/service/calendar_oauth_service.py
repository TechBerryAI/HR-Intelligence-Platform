"""Google Calendar OAuth connect / refresh for recruiters."""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from app.domains.integrations.company_context import resolve_company_for_user
from app.domains.integrations.provider.calendar_factory import get_calendar_provider
from app.domains.integrations.provider.google_calendar import (
    build_google_auth_url,
    exchange_code_for_tokens,
    google_oauth_configured,
)
from app.domains.integrations.provider.calendar_base import OAuthTokenBundle
from app.domains.integrations.repository import oauth_tokens as oauth_repo
from app.domains.identity.authorization.rbac import get_user_id

logger = logging.getLogger(__name__)

PROVIDER = oauth_repo.PROVIDER_GOOGLE_CALENDAR

# In-process OAuth state → hrid (swap-ready for Redis)
_oauth_states: dict[str, dict] = {}


def _frontend_settings_url() -> str:
    base = (os.getenv('FRONTEND_URL') or 'http://localhost:5173').rstrip('/')
    return f'{base}/settings?tab=integrations'


def start_oauth(user: dict) -> tuple[str | None, str | None]:
    """Return (auth_url, error)."""
    if not google_oauth_configured():
        return None, 'Google OAuth is not configured (GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI)'
    hrid = get_user_id(user)
    if not hrid:
        return None, 'User id required'
    company_key, _ = resolve_company_for_user(user)
    if not company_key:
        return None, 'Company context required'
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = {
        'hrid': hrid,
        'company_key': company_key,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    return build_google_auth_url(state), None


def handle_oauth_callback(code: str | None, state: str | None) -> tuple[str, str | None]:
    """
    Exchange code, store tokens.
    Returns (redirect_url, error_message).
    """
    redirect = _frontend_settings_url()
    if not code or not state:
        return f'{redirect}&calendar=error', 'Missing code or state'
    ctx = _oauth_states.pop(state, None)
    if not ctx:
        return f'{redirect}&calendar=error', 'Invalid or expired OAuth state'
    try:
        data = exchange_code_for_tokens(code)
    except Exception as exc:
        logger.exception('[calendar_oauth] token exchange failed')
        return f'{redirect}&calendar=error', str(exc)

    access = data.get('access_token')
    if not access:
        return f'{redirect}&calendar=error', 'No access token returned'
    refresh = data.get('refresh_token')
    expires_in = int(data.get('expires_in') or 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    oauth_repo.upsert_oauth_tokens(
        provider=PROVIDER,
        hrid=ctx['hrid'],
        company_key=ctx['company_key'],
        access_token=access,
        refresh_token=refresh,
        expires_at=expires_at,
        token_type=data.get('token_type') or 'Bearer',
        scope=data.get('scope'),
        raw_json=data,
    )
    return f'{redirect}&calendar=connected', None


def get_connection_status(hrid: str) -> dict:
    row = oauth_repo.get_oauth_row(PROVIDER, hrid)
    if not row:
        return {
            'connected': False,
            'configured': google_oauth_configured(),
            'provider': PROVIDER,
        }
    return {
        'connected': True,
        'configured': google_oauth_configured(),
        'provider': PROVIDER,
        'expiresAt': row.get('expires_at').isoformat()
        if getattr(row.get('expires_at'), 'isoformat', None)
        else row.get('expires_at'),
        'updatedAt': row.get('updated_at').isoformat()
        if getattr(row.get('updated_at'), 'isoformat', None)
        else row.get('updated_at'),
    }


def disconnect(hrid: str) -> None:
    oauth_repo.delete_oauth_tokens(PROVIDER, hrid)


def load_valid_tokens(hrid: str) -> OAuthTokenBundle | None:
    """Load tokens for hrid, refreshing access token if expired."""
    row = oauth_repo.get_oauth_row(PROVIDER, hrid)
    tokens = oauth_repo.row_to_token_bundle(row)
    if not tokens:
        return None
    if not oauth_repo.is_token_expired(tokens):
        return tokens
    provider = get_calendar_provider(PROVIDER)
    if not provider or not tokens.refresh_token:
        return None
    try:
        refreshed = provider.refresh_access_token(tokens)
    except Exception:
        logger.exception('[calendar_oauth] refresh failed for hrid=%s', hrid)
        return None
    company_key = (row or {}).get('company_key') or 'unknown'
    oauth_repo.upsert_oauth_tokens(
        provider=PROVIDER,
        hrid=hrid,
        company_key=company_key,
        access_token=refreshed.access_token,
        refresh_token=refreshed.refresh_token,
        expires_at=refreshed.expires_at,
        token_type=refreshed.token_type,
        scope=refreshed.scope,
        raw_json=refreshed.raw,
    )
    return refreshed
