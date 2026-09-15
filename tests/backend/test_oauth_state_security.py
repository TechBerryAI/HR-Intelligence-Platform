"""OAuth CSRF-state security matrix for the Google Calendar connect flow.

Runs against live PostgreSQL (the ``oauth_csrf_state`` DB-fallback path used
whenever Redis is unavailable) — no DB mocks for the state-consumption
boundary itself. Redis is force-disabled here so every test exercises the
fallback table directly, including the atomic delete-and-return fix for the
SELECT-then-DELETE replay race (see calendar_oauth_service._pop_oauth_state).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from live_db_helpers import app_client, seed_org_with_staff  # noqa: F401

from app.core import shared_store
from app.database.connection.db import db_get, db_run
from app.domains.integrations.service import calendar_oauth_service as svc


@pytest.fixture(autouse=True)
def _force_redis_down(monkeypatch):
    """Route state storage/consumption through the Postgres fallback table."""
    monkeypatch.setattr(shared_store, 'redis_status', lambda: 'down')


@pytest.fixture(autouse=True)
def _google_oauth_configured(monkeypatch):
    monkeypatch.setenv('GOOGLE_OAUTH_CLIENT_ID', 'test-client-id')
    monkeypatch.setenv('GOOGLE_OAUTH_CLIENT_SECRET', 'test-client-secret')
    monkeypatch.setenv('GOOGLE_OAUTH_REDIRECT_URI', 'http://localhost:5000/api/integrations/calendar/google/callback')


@pytest.fixture(autouse=True)
def _fake_token_exchange(monkeypatch):
    monkeypatch.setattr(
        svc,
        'exchange_code_for_tokens',
        lambda code: {'access_token': f'access-for-{code}', 'refresh_token': 'refresh-1', 'expires_in': 3600},
    )


def _recruiter_user(seed: dict) -> dict:
    return {'user_id': seed['recruiter_hrid'], 'role': 'RECRUITER', 'company': seed['org_name']}


def test_valid_state_succeeds_and_binds_to_correct_org(app_client):
    a = seed_org_with_staff()
    url, err = svc.start_oauth(_recruiter_user(a), return_to=None)
    assert err is None and url

    state = url.split('state=')[1].split('&')[0]
    redirect, err = svc.handle_oauth_callback('good-code', state)
    assert err is None, err

    from app.domains.integrations.repository import oauth_tokens as oauth_repo

    row = oauth_repo.get_oauth_row(svc.PROVIDER, a['recruiter_hrid'])
    assert row is not None
    assert str(row['organization_id']) == a['org_id']


def test_reused_state_fails_single_use_enforced(app_client):
    a = seed_org_with_staff()
    url, _ = svc.start_oauth(_recruiter_user(a), return_to=None)
    state = url.split('state=')[1].split('&')[0]

    _redirect1, err1 = svc.handle_oauth_callback('code-1', state)
    assert err1 is None

    # Replay with the same (now-consumed) state must be rejected.
    _redirect2, err2 = svc.handle_oauth_callback('code-2', state)
    assert err2 == 'Invalid or expired OAuth state'


def test_expired_state_fails(app_client):
    a = seed_org_with_staff()
    state = 'expired-state-token'
    payload = {
        'hrid': a['recruiter_hrid'],
        'organization_id': a['org_id'],
        'return_to': None,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    import json

    db_run(
        """
        INSERT INTO oauth_csrf_state (state, payload_json, expires_at)
        VALUES (?, ?::jsonb, NOW() - INTERVAL '1 second')
        """,
        (state, json.dumps(payload)),
    )
    _redirect, err = svc.handle_oauth_callback('some-code', state)
    assert err == 'Invalid or expired OAuth state'
    # Expired row must be reaped, not left queryable forever.
    assert db_get('SELECT state FROM oauth_csrf_state WHERE state = ?', (state,)) is None


def test_forged_unknown_state_fails(app_client):
    _redirect, err = svc.handle_oauth_callback('some-code', 'totally-forged-state-value')
    assert err == 'Invalid or expired OAuth state'


def test_missing_state_fails(app_client):
    _redirect, err = svc.handle_oauth_callback('some-code', None)
    assert err == 'Missing code or state'


def test_stale_state_binds_current_org_not_payload_org(app_client):
    """Even if a state row's stored organization_id were tampered with (or
    simply stale after an org change), the callback must re-resolve org_id
    from the DB for the state's hrid — never trust the payload's org id."""
    a = seed_org_with_staff()
    b = seed_org_with_staff()
    url, _ = svc.start_oauth(_recruiter_user(a), return_to=None)
    state = url.split('state=')[1].split('&')[0]

    # Tamper with the persisted payload to claim org B instead of org A.
    row = db_get('SELECT payload_json FROM oauth_csrf_state WHERE state = ?', (state,))
    assert row is not None
    tampered = dict(row['payload_json'])
    tampered['organization_id'] = b['org_id']
    import json

    db_run(
        'UPDATE oauth_csrf_state SET payload_json = ?::jsonb WHERE state = ?',
        (json.dumps(tampered), state),
    )

    _redirect, err = svc.handle_oauth_callback('some-code', state)
    assert err is None

    from app.domains.integrations.repository import oauth_tokens as oauth_repo

    row = oauth_repo.get_oauth_row(svc.PROVIDER, a['recruiter_hrid'])
    assert row is not None
    # Tokens are attributed to org A (the recruiter's real org), never org B.
    assert str(row['organization_id']) == a['org_id']
    assert str(row['organization_id']) != b['org_id']


def test_malicious_return_to_is_not_honored(app_client):
    a = seed_org_with_staff()
    url, _ = svc.start_oauth(_recruiter_user(a), return_to='https://evil.example.com/steal')
    state = url.split('state=')[1].split('&')[0]

    redirect, err = svc.handle_oauth_callback('some-code', state)
    assert err is None
    assert 'evil.example.com' not in redirect


def test_concurrent_pop_only_one_winner(app_client):
    """Regression for the SELECT-then-DELETE race: simulate two callback
    requests racing on the same state — only one may consume it."""
    a = seed_org_with_staff()
    state = 'race-state-token'
    payload = {'hrid': a['recruiter_hrid'], 'organization_id': a['org_id'], 'return_to': None}
    import json

    db_run(
        """
        INSERT INTO oauth_csrf_state (state, payload_json, expires_at)
        VALUES (?, ?::jsonb, NOW() + INTERVAL '600 seconds')
        """,
        (state, json.dumps(payload)),
    )

    first = svc._pop_oauth_state(state)
    second = svc._pop_oauth_state(state)
    assert first is not None
    assert second is None
