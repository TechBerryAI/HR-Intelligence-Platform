"""optional_authenticate_token treats bad tokens as anonymous (not 401)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import jwt
import pytest
from flask import Flask, jsonify, request

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault('JWT_SECRET', 'test-optional-auth-secret')

from app.api.middleware.auth import optional_authenticate_token  # noqa: E402
from app.core.auth import JWT_SECRET  # noqa: E402


@pytest.fixture
def client():
    app = Flask(__name__)

    @app.get('/public')
    @optional_authenticate_token
    def public_route():
        user = getattr(request, 'user', None)
        return jsonify({'authenticated': user is not None, 'ok': True})

    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_optional_auth_no_token_is_anonymous(client):
    resp = client.get('/public')
    assert resp.status_code == 200
    assert resp.get_json() == {'authenticated': False, 'ok': True}


def test_optional_auth_expired_token_is_anonymous(client):
    token = jwt.encode(
        {'sub': 'u1', 'exp': 1},
        JWT_SECRET,
        algorithm='HS256',
    )
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    resp = client.get('/public', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json() == {'authenticated': False, 'ok': True}


def test_optional_auth_garbage_token_is_anonymous(client):
    resp = client.get('/public', headers={'Authorization': 'Bearer not-a-jwt'})
    assert resp.status_code == 200
    assert resp.get_json() == {'authenticated': False, 'ok': True}


def test_optional_auth_refresh_token_is_anonymous(client):
    token = jwt.encode(
        {'sub': 'u1', 'type': 'refresh'},
        JWT_SECRET,
        algorithm='HS256',
    )
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    resp = client.get('/public', headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 200
    assert resp.get_json() == {'authenticated': False, 'ok': True}
