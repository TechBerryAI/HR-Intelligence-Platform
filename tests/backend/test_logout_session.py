"""Logout must not report success when revoke fails."""
from __future__ import annotations

import jwt

from app.core.auth import JWT_SECRET
from app.domains.identity.sessions import service as sessions_service
from app.domains.identity.sessions.service import deactivate_session


def test_deactivate_session_rejects_empty_token():
    result = deactivate_session('')
    assert result.get('success') is False
    assert result.get('error')


def test_deactivate_session_rejects_garbage_token():
    result = deactivate_session('not-a-jwt')
    assert result.get('success') is False
    assert result.get('error')


def test_deactivate_session_rejects_token_belonging_to_another_user():
    """POST /sessions/logout-session must not let an authenticated caller
    revoke a DIFFERENT user's session by supplying that user's (still
    validly-signed, e.g. leaked/expired) token in the request body."""
    victim_token = jwt.encode(
        {'user_id': 'victim-hrid', 'type': 'refresh', 'jti': 'victim-jti'},
        JWT_SECRET,
        algorithm='HS256',
    )
    result = deactivate_session(victim_token, expected_user_id='attacker-hrid')
    assert result.get('success') is False
    assert 'does not belong' in (result.get('error') or '')


def test_deactivate_session_allows_callers_own_token(monkeypatch):
    revoked = {}

    def _fake_revoke(token):
        revoked['token'] = token
        return {'success': True}

    monkeypatch.setattr(sessions_service, 'revoke_refresh_token', _fake_revoke)
    own_token = jwt.encode(
        {'user_id': 'own-hrid', 'type': 'refresh', 'jti': 'own-jti'},
        JWT_SECRET,
        algorithm='HS256',
    )
    result = deactivate_session(own_token, expected_user_id='own-hrid')
    assert result.get('success') is True
    assert revoked.get('token') == own_token


def test_deactivate_session_without_expected_user_id_is_unrestricted(monkeypatch):
    """Self-service (unauthenticated) callers in hr_auth.py omit
    expected_user_id — the supplied token is the only identity in play."""
    revoked = {}

    def _fake_revoke(token):
        revoked['token'] = token
        return {'success': True}

    monkeypatch.setattr(sessions_service, 'revoke_refresh_token', _fake_revoke)
    token = jwt.encode(
        {'user_id': 'someone', 'type': 'refresh', 'jti': 'jti-x'},
        JWT_SECRET,
        algorithm='HS256',
    )
    # No expected_user_id passed -> ownership check is skipped; behavior is
    # unchanged from before this fix (still goes on to attempt the revoke).
    result = deactivate_session(token)
    assert result.get('success') is True
    assert revoked.get('token') == token
