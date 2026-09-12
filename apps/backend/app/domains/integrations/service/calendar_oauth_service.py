"""Google Calendar OAuth connect / refresh for recruiters."""
from __future__ import annotations

import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.core import shared_store
from app.database.connection.db import db_get, db_run
from app.domains.integrations.company_context import resolve_organization_for_user
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
_OAUTH_STATE_TTL_SEC = int(os.getenv('OAUTH_STATE_TTL_SEC', '600'))
_OAUTH_STATE_PREFIX = 'oauth:calendar:state:'


def _put_oauth_state(state: str, payload: dict) -> None:
    key = f'{_OAUTH_STATE_PREFIX}{state}'
    if shared_store.redis_status() == 'ok':
        shared_store.set_json(key, payload, ttl_seconds=_OAUTH_STATE_TTL_SEC)
        return
    # Multi-worker safe fallback when Redis is down
    import json

    db_run(
        """
        INSERT INTO oauth_csrf_state (state, payload_json, expires_at)
        VALUES (?, ?::jsonb, NOW() + (? * INTERVAL '1 second'))
        ON CONFLICT (state) DO UPDATE SET
            payload_json = EXCLUDED.payload_json,
            expires_at = EXCLUDED.expires_at
        """,
        (state, json.dumps(payload), _OAUTH_STATE_TTL_SEC),
    )


def _pop_oauth_state(state: str | None) -> dict | None:
    if not state:
        return None
    key = f'{_OAUTH_STATE_PREFIX}{state}'
    if shared_store.redis_status() == 'ok':
        ctx = shared_store.pop_json(key)
        if ctx:
            return ctx
    row = db_get(
        """
        SELECT payload_json FROM oauth_csrf_state
        WHERE state = ? AND expires_at > NOW()
        """,
        (state,),
    )
    db_run('DELETE FROM oauth_csrf_state WHERE state = ?', (state,))
    if not row:
        return None
    payload = row.get('payload_json')
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        import json

        try:
            data = json.loads(payload)
            return data if isinstance(data, dict) else None
        except Exception:
            return None
    return None

_ALLOWED_RETURN_PATHS = frozenset({'/settings', '/head-hr/settings'})
_DEBUG_ORIGIN_RE = re.compile(
    r'^http://('
    r'localhost|'
    r'127\.0\.0\.1|'
    r'192\.168\.\d{1,3}\.\d{1,3}|'
    r'10\.\d{1,3}\.\d{1,3}\.\d{1,3}|'
    r'172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}'
    r'):\d+$'
)


def _configured_frontend_origins() -> list[str]:
    raw = os.getenv('FRONTEND_URLS') or os.getenv('FRONTEND_URL') or ''
    origins = [o.strip().rstrip('/') for o in raw.split(',') if o.strip()]
    primary = (os.getenv('FRONTEND_URL') or '').strip().rstrip('/')
    if primary and primary not in origins:
        origins.insert(0, primary)
    if not origins:
        origins = ['http://localhost:5173', 'http://127.0.0.1:5173']
    return origins


def _origin_allowed(origin: str) -> bool:
    origin = (origin or '').rstrip('/')
    if not origin:
        return False
    if origin in _configured_frontend_origins():
        return True
    if os.getenv('FLASK_DEBUG', 'false').lower() == 'true':
        return bool(_DEBUG_ORIGIN_RE.match(origin))
    return False


def sanitize_oauth_return_to(return_to: str | None) -> str | None:
    """Allow only same-app settings URLs on configured (or local-debug) origins."""
    if not return_to or not isinstance(return_to, str):
        return None
    try:
        parsed = urlparse(return_to.strip())
    except Exception:
        return None
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return None
    origin = f'{parsed.scheme}://{parsed.netloc}'.rstrip('/')
    if not _origin_allowed(origin):
        return None
    path = parsed.path or '/'
    if path.endswith('/') and path != '/':
        path = path.rstrip('/')
    if path not in _ALLOWED_RETURN_PATHS:
        return None
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query['tab'] = 'integrations'
    return urlunparse((parsed.scheme, parsed.netloc, path, '', urlencode(query), ''))


def _frontend_settings_url(return_to: str | None = None) -> str:
    sanitized = sanitize_oauth_return_to(return_to)
    if sanitized:
        return sanitized
    base = (os.getenv('FRONTEND_URL') or 'http://localhost:5173').rstrip('/')
    return f'{base}/settings?tab=integrations'


def start_oauth(user: dict, return_to: str | None = None) -> tuple[str | None, str | None]:
    """Return (auth_url, error)."""
    if not google_oauth_configured():
        return None, 'Google OAuth is not configured (GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI)'
    hrid = get_user_id(user)
    if not hrid:
        return None, 'User id required'
    organization_id, _ = resolve_organization_for_user(user)
    if not organization_id:
        return None, 'Company context required'
    state = secrets.token_urlsafe(24)
    payload = {
        'hrid': hrid,
        'organization_id': organization_id,
        'return_to': sanitize_oauth_return_to(return_to),
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    try:
        _put_oauth_state(state, payload)
    except Exception as exc:
        logger.exception('[calendar_oauth] failed to persist OAuth state')
        return None, f'Unable to start OAuth ({exc})'
    return build_google_auth_url(state), None


def handle_oauth_callback(code: str | None, state: str | None) -> tuple[str, str | None]:
    """
    Exchange code, store tokens.
    Returns (redirect_url, error_message).
    """
    ctx = _pop_oauth_state(state)
    redirect = _frontend_settings_url((ctx or {}).get('return_to'))
    if not code or not state:
        return f'{redirect}&calendar=error', 'Missing code or state'
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

    # Re-resolve organization_id from the DB for this hrid at callback time —
    # never trust the org id carried in the (popped, single-use) state blob,
    # so a stale/forged state cannot bind tokens to the wrong tenant.
    from app.domains.identity.services.organizations import get_organization_id_for_user

    organization_id = get_organization_id_for_user({'user_id': ctx['hrid']})
    if not organization_id:
        return f'{redirect}&calendar=error', 'Unable to verify company context for this account'

    refresh = data.get('refresh_token')
    expires_in = int(data.get('expires_in') or 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    oauth_repo.upsert_oauth_tokens(
        provider=PROVIDER,
        hrid=ctx['hrid'],
        organization_id=organization_id,
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
    organization_id = (row or {}).get('organization_id')
    if not organization_id:
        from app.domains.identity.services.organizations import get_organization_id_for_user

        organization_id = get_organization_id_for_user({'user_id': hrid})
    if not organization_id:
        logger.warning('[calendar_oauth] refresh aborted — no organization_id for hrid=%s', hrid)
        return None
    oauth_repo.upsert_oauth_tokens(
        provider=PROVIDER,
        hrid=hrid,
        organization_id=str(organization_id),
        company_key=(row or {}).get('company_key'),
        access_token=refreshed.access_token,
        refresh_token=refreshed.refresh_token,
        expires_at=refreshed.expires_at,
        token_type=refreshed.token_type,
        scope=refreshed.scope,
        raw_json=refreshed.raw,
    )
    return refreshed
