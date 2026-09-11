"""Shared helpers for live-PostgreSQL backend security tests."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import bcrypt
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

STRONG_PASSWORD = 'Str0ng!Pass9'


def _require_database():
    if not (os.getenv('DATABASE_URL') or '').strip():
        if not (os.getenv('POSTGRES_USER') and os.getenv('POSTGRES_PASSWORD')):
            pytest.skip('DATABASE_URL required for live DB tests')


@pytest.fixture(scope='module')
def app_client():
    _require_database()
    os.environ.setdefault('FLASK_DEBUG', 'true')
    os.environ.setdefault('ALLOW_INSECURE_JWT', 'true')
    os.environ.setdefault('JWT_SECRET', 'ci-test-jwt-secret-at-least-32-characters-long')
    os.environ.setdefault('MAIL_SUPPRESS_SEND', 'true')
    os.environ.setdefault('PLATFORM_PROVISION_KEY', 'test-platform-key-for-ci')
    try:
        from wsgi import app
    except Exception as exc:
        pytest.skip(f'Flask app unavailable: {exc}')
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def unique_slug(prefix: str = 'org') -> str:
    return f'{prefix}-{uuid.uuid4().hex[:10]}'


def unique_email(domain: str = 'example.com') -> str:
    return f'u-{uuid.uuid4().hex[:10]}@{domain}'


def hash_password(password: str = STRONG_PASSWORD) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def seed_org_with_staff(
    *,
    name: str | None = None,
    head_email: str | None = None,
    ceo_email: str | None = None,
    recruiter_email: str | None = None,
    password: str = STRONG_PASSWORD,
):
    """Insert org + HEAD_HR (+ optional CEO/recruiter). Returns dict of ids/emails."""
    from app.database.connection.db import db_get, db_run
    from app.domains.identity.services.hrid import next_hrid
    from app.domains.identity.services.organizations import ensure_organization, slugify_company

    display = name or f'Test Co {uuid.uuid4().hex[:6]}'
    # Force unique slug by using create_only name that slugifies uniquely
    slug_name = display if name else f'TestCo{uuid.uuid4().hex[:8]}'
    org_id = ensure_organization(slug_name, create_only=True)
    org = db_get('SELECT id, name, slug FROM organizations WHERE id = ?', (org_id,))
    pw = hash_password(password)

    def _insert(role: str, email: str, full_name: str) -> str:
        hrid = next_hrid()
        db_run(
            """
            INSERT INTO hr_signup (
                hrid, full_name, email, company, password, role,
                account_status, organization_id
            ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
            """,
            (hrid, full_name, email, org['name'], pw, role, org_id),
        )
        return hrid

    head_email = head_email or unique_email()
    head_id = _insert('HEAD_HR', head_email, 'Head HR')
    ceo_id = None
    if ceo_email is not False:
        ceo_email = ceo_email or unique_email()
        ceo_id = _insert('CEO', ceo_email, 'CEO User')
    peer_id = None
    peer_email = unique_email()
    peer_id = _insert('HEAD_HR', peer_email, 'Peer Head')
    recruiter_email = recruiter_email or unique_email()
    recruiter_id = _insert('RECRUITER', recruiter_email, 'Recruiter User')

    return {
        'org_id': str(org_id),
        'org_name': org['name'],
        'org_slug': org['slug'] or slugify_company(slug_name),
        'head_hrid': head_id,
        'head_email': head_email,
        'ceo_hrid': ceo_id,
        'ceo_email': ceo_email,
        'peer_hrid': peer_id,
        'peer_email': peer_email,
        'recruiter_hrid': recruiter_id,
        'recruiter_email': recruiter_email,
        'password': password,
    }


def login(client, email: str, password: str = STRONG_PASSWORD) -> str:
    resp = client.post('/api/login', json={'email': email, 'password': password})
    assert resp.status_code == 200, resp.get_json()
    token = (resp.get_json() or {}).get('token')
    assert token
    return token


def auth_header(token: str) -> dict:
    return {'Authorization': f'Bearer {token}'}


def seed_job(org_id: str, posted_by: str, *, title: str = 'Engineer', enabled: bool = True) -> str:
    from app.database.connection.db import db_run

    jdid = f'JD{uuid.uuid4().hex[:10].upper()}'
    db_run(
        """
        INSERT INTO jobs (
            jdid, title, company, location, description, posted_by, organization_id, enabled, posted_on, status
        )
        VALUES (?, ?, 'Test Co', 'Remote', 'Test job description', ?, ?, ?, NOW(), 'Published')
        """,
        (jdid, title, posted_by, org_id, enabled),
    )
    return jdid
