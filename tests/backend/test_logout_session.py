"""Logout must not report success when revoke fails."""
from __future__ import annotations

from app.domains.identity.sessions.service import deactivate_session


def test_deactivate_session_rejects_empty_token():
    result = deactivate_session('')
    assert result.get('success') is False
    assert result.get('error')


def test_deactivate_session_rejects_garbage_token():
    result = deactivate_session('not-a-jwt')
    assert result.get('success') is False
    assert result.get('error')
