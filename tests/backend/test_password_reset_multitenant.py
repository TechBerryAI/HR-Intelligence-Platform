"""Password-reset domain allowlist and anti-enumeration."""
from __future__ import annotations

from live_db_helpers import app_client, seed_org_with_staff, unique_email


def test_forgot_password_identical_for_unknown(app_client, monkeypatch):
    monkeypatch.setenv('ALLOWED_PASSWORD_RESET_DOMAINS', '')
    # Reload allowlist by calling through already-imported module after patching env
    import app.domains.identity.api.hr_auth as hr_auth

    monkeypatch.setattr(hr_auth, 'ALLOWED_PASSWORD_RESET_DOMAINS_RAW', '')

    org = seed_org_with_staff()
    known = org['recruiter_email']
    unknown = unique_email()

    r1 = app_client.post('/api/forgot-password', json={'email': known})
    r2 = app_client.post('/api/forgot-password', json={'email': unknown})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.get_data() == r2.get_data()


def test_forgot_password_second_tenant_domain(app_client, monkeypatch):
    import app.domains.identity.api.hr_auth as hr_auth

    monkeypatch.setattr(hr_auth, 'ALLOWED_PASSWORD_RESET_DOMAINS_RAW', '')
    org = seed_org_with_staff()
    # Replace recruiter email domain
    from app.database.connection.db import db_run
    from live_db_helpers import unique_email

    email = unique_email('customer-two.io')
    db_run('UPDATE hr_signup SET email = ? WHERE hrid = ?', (email, org['recruiter_hrid']))
    resp = app_client.post('/api/forgot-password', json={'email': email})
    assert resp.status_code == 200
