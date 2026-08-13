"""Regression: OAuth secrets never land in raw_json; encryption fails closed."""
from __future__ import annotations

import json
import os

import pytest

from app.domains.integrations.repository.oauth_tokens import sanitize_oauth_raw_json
from app.domains.integrations.security.secrets import (
    IntegrationSecretsError,
    decrypt_secret,
    encrypt_secret,
)


def test_sanitize_oauth_raw_json_strips_secrets():
    raw = {
        'access_token': 'ya29.secret',
        'refresh_token': '1//secret',
        'id_token': 'eyJ.secret',
        'client_secret': 'goog-secret',
        'authorization_code': 'code',
        'token_type': 'Bearer',
        'scope': 'calendar',
        'expires_in': 3600,
    }
    safe = sanitize_oauth_raw_json(raw)
    assert safe == {
        'token_type': 'Bearer',
        'scope': 'calendar',
        'expires_in': 3600,
    }
    blob = json.dumps(safe)
    assert 'ya29' not in blob
    assert '1//' not in blob
    assert 'eyJ' not in blob


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setenv('INTEGRATION_SECRETS_KEY', 'unit-test-integration-secrets-key-32b')
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_INSECURE_INTEGRATION_SECRETS', 'false')
    enc = encrypt_secret('plain-access-token')
    assert enc is not None
    assert enc.startswith('enc:v1:')
    assert 'plain-access-token' not in enc
    assert decrypt_secret(enc) == 'plain-access-token'


def test_encrypt_fails_closed_without_key(monkeypatch):
    monkeypatch.delenv('INTEGRATION_SECRETS_KEY', raising=False)
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_INSECURE_INTEGRATION_SECRETS', 'false')
    # Clear any JWT fallback usefulness by ensuring insecure mode is off
    with pytest.raises(IntegrationSecretsError):
        encrypt_secret('must-not-store-plaintext')


def test_upsert_oauth_tokens_scrubs_and_encrypts(monkeypatch):
    from app.domains.integrations.repository import oauth_tokens as repo

    stored = {}

    monkeypatch.setenv('INTEGRATION_SECRETS_KEY', 'unit-test-integration-secrets-key-32b')
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_INSECURE_INTEGRATION_SECRETS', 'false')

    monkeypatch.setattr(repo, 'get_oauth_row', lambda *a, **k: None)

    def fake_db_run(sql, params=None):
        stored['sql'] = sql
        stored['params'] = params

    monkeypatch.setattr(repo, 'db_run', fake_db_run)

    from datetime import datetime, timezone

    repo.upsert_oauth_tokens(
        provider='google_calendar',
        hrid='HR001',
        company_key='acme',
        access_token='ya29.access',
        refresh_token='1//refresh',
        expires_at=datetime.now(timezone.utc),
        token_type='Bearer',
        scope='calendar',
        raw_json={
            'access_token': 'ya29.access',
            'refresh_token': '1//refresh',
            'id_token': 'eyJ.id',
            'token_type': 'Bearer',
            'scope': 'calendar',
            'expires_in': 3600,
        },
    )
    params = stored['params']
    access_col, refresh_col, raw_col = params[3], params[4], params[8]
    assert access_col.startswith('enc:v1:')
    assert refresh_col.startswith('enc:v1:')
    assert 'ya29' not in access_col
    raw = json.loads(raw_col)
    assert 'access_token' not in raw
    assert 'refresh_token' not in raw
    assert 'id_token' not in raw
    assert raw.get('scope') == 'calendar'
