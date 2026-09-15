"""Platform provisioning must 409 on colliding company slugs."""
from __future__ import annotations

import os
import uuid

from live_db_helpers import STRONG_PASSWORD, app_client, unique_email


def test_org_provisioning_collisions(app_client):
    os.environ['PLATFORM_PROVISION_KEY'] = 'test-platform-key-for-ci'
    headers = {'X-Platform-Key': 'test-platform-key-for-ci'}
    tag = uuid.uuid4().hex[:6]
    base = f'Acme{tag} Corp LLC'

    first = app_client.post(
        '/api/platform/companies',
        headers=headers,
        json={
            'name': base,
            'headHr': {
                'email': unique_email('acme-test.com'),
                'fullName': 'Head One',
                'password': STRONG_PASSWORD,
            },
        },
    )
    assert first.status_code == 201, first.get_json()
    slug = first.get_json()['company']['slug']
    assert slug == f'acme{tag}-corp'

    from app.database.connection.db import db_get
    from app.domains.identity.services.organizations import slugify_company

    variants = [
        f'Acme{tag} Corp',
        f'ACME{tag} Corp.',
        f'Acme{tag} Corp Pvt Ltd',
        f'Acme{tag} Corp Inc',
        f'Acme{tag} Corp!!!',
    ]
    for name in variants:
        assert slugify_company(name) == slug
        before = db_get('SELECT COUNT(*) AS cnt FROM hr_signup')
        resp = app_client.post(
            '/api/platform/companies',
            headers=headers,
            json={
                'name': name,
                'headHr': {
                    'email': unique_email('acme-test.com'),
                    'fullName': 'Head Two',
                    'password': STRONG_PASSWORD,
                },
            },
        )
        assert resp.status_code == 409, (name, resp.get_json())
        assert slug in (resp.get_json().get('slug') or resp.get_json().get('error') or '')
        after = db_get('SELECT COUNT(*) AS cnt FROM hr_signup')
        assert after['cnt'] == before['cnt']
