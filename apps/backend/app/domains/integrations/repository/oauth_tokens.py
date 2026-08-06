"""Persistence for per-recruiter OAuth calendar tokens."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.database.connection.db import db_get, db_run
from app.domains.integrations.provider.calendar_base import OAuthTokenBundle
from app.domains.integrations.security.secrets import decrypt_secret, encrypt_secret

PROVIDER_GOOGLE_CALENDAR = 'google_calendar'


def get_oauth_row(provider: str, hrid: str) -> dict | None:
    return db_get(
        '''
        SELECT * FROM oauth_tokens
        WHERE provider = ? AND hrid = ?
        ''',
        (provider, hrid),
    )


def delete_oauth_tokens(provider: str, hrid: str) -> None:
    db_run(
        'DELETE FROM oauth_tokens WHERE provider = ? AND hrid = ?',
        (provider, hrid),
    )


def upsert_oauth_tokens(
    *,
    provider: str,
    hrid: str,
    company_key: str,
    access_token: str,
    refresh_token: str | None,
    expires_at: datetime | None,
    token_type: str = 'Bearer',
    scope: str | None = None,
    raw_json: dict | None = None,
) -> None:
    enc_access = encrypt_secret(access_token)
    enc_refresh = encrypt_secret(refresh_token) if refresh_token else None
    raw = json.dumps(raw_json) if raw_json is not None else None
    existing = get_oauth_row(provider, hrid)
    if existing:
        # Preserve refresh_token if Google omitted it on refresh
        if not enc_refresh and existing.get('refresh_token'):
            enc_refresh = existing['refresh_token']
        db_run(
            '''
            UPDATE oauth_tokens
            SET company_key = ?,
                access_token = ?,
                refresh_token = ?,
                token_type = ?,
                scope = ?,
                expires_at = ?,
                raw_json = ?,
                updated_at = NOW()
            WHERE provider = ? AND hrid = ?
            ''',
            (
                company_key,
                enc_access,
                enc_refresh,
                token_type,
                scope,
                expires_at,
                raw,
                provider,
                hrid,
            ),
        )
        return

    db_run(
        '''
        INSERT INTO oauth_tokens (
            company_key, provider, hrid, access_token, refresh_token,
            token_type, scope, expires_at, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            company_key,
            provider,
            hrid,
            enc_access,
            enc_refresh,
            token_type,
            scope,
            expires_at,
            raw,
        ),
    )


def row_to_token_bundle(row: dict | None) -> OAuthTokenBundle | None:
    if not row or not row.get('access_token'):
        return None
    access = decrypt_secret(row.get('access_token'))
    refresh = decrypt_secret(row.get('refresh_token')) if row.get('refresh_token') else None
    if not access:
        return None
    expires_at = row.get('expires_at')
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        except ValueError:
            expires_at = None
    raw: dict[str, Any] = {}
    raw_json = row.get('raw_json')
    if isinstance(raw_json, dict):
        raw = raw_json
    elif isinstance(raw_json, str) and raw_json:
        try:
            raw = json.loads(raw_json) or {}
        except json.JSONDecodeError:
            raw = {}
    return OAuthTokenBundle(
        access_token=access,
        refresh_token=refresh,
        expires_at=expires_at,
        token_type=row.get('token_type') or 'Bearer',
        scope=row.get('scope'),
        raw=raw,
    )


def is_token_expired(tokens: OAuthTokenBundle, skew_seconds: int = 60) -> bool:
    if not tokens.expires_at:
        return False
    exp = tokens.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    from datetime import timedelta

    return exp <= datetime.now(timezone.utc) + timedelta(seconds=skew_seconds)
