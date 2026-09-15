"""PUT/DELETE admin mutation matrix against live PostgreSQL (no db mocks)."""
from __future__ import annotations

import pytest

from live_db_helpers import (
    STRONG_PASSWORD,
    app_client,
    auth_header,
    login,
    seed_org_with_staff,
)

pytestmark = pytest.mark.usefixtures('app_client')


@pytest.fixture(scope='module')
def tenants(app_client):
    a = seed_org_with_staff()
    b = seed_org_with_staff()
    return a, b


def _password_of(hrid: str) -> str | None:
    from app.database.connection.db import db_get

    row = db_get('SELECT password FROM hr_signup WHERE hrid = ?', (hrid,))
    return row['password'] if row else None


@pytest.mark.parametrize('method', ['PUT', 'DELETE'])
@pytest.mark.parametrize(
    'target_key,expected',
    [
        ('self', 403),
        ('ceo', 403),
        ('peer', 403),
        ('recruiter', 200),
        ('cross', 404),
    ],
)
def test_admin_mutation_matrix(app_client, tenants, method, target_key, expected):
    a, b = tenants
    token = login(app_client, a['head_email'])
    headers = auth_header(token)

    targets = {
        'self': a['head_hrid'],
        'ceo': a['ceo_hrid'],
        'peer': a['peer_hrid'],
        'recruiter': a['recruiter_hrid'],
        'cross': b['recruiter_hrid'],
    }
    hrid = targets[target_key]

    ceo_pw_before = _password_of(a['ceo_hrid'])

    if method == 'PUT':
        # Fresh recruiter for PUT success path so DELETE cases don't collide
        if target_key == 'recruiter':
            from live_db_helpers import unique_email, hash_password
            from app.database.connection.db import db_run
            from app.domains.identity.services.hrid import next_hrid

            rid = next_hrid()
            db_run(
                """
                INSERT INTO hr_signup (
                    hrid, full_name, email, company, password, role,
                    account_status, organization_id
                ) VALUES (?, 'Temp Rec', ?, ?, ?, 'RECRUITER', 'active', ?)
                """,
                (rid, unique_email(), a['org_name'], hash_password(), a['org_id']),
            )
            hrid = rid
        resp = app_client.put(
            f'/api/head-hr/admins/{hrid}',
            headers=headers,
            json={'fullName': 'Updated Name', 'password': STRONG_PASSWORD + 'x'},
        )
    else:
        # Ensure recruiter active for DELETE 200
        if target_key == 'recruiter':
            from app.database.connection.db import db_run

            db_run(
                "UPDATE hr_signup SET account_status = 'active' WHERE hrid = ?",
                (hrid,),
            )
        resp = app_client.delete(f'/api/head-hr/admins/{hrid}', headers=headers)

    assert resp.status_code == expected, (method, target_key, resp.get_json())

    if target_key == 'ceo':
        assert _password_of(a['ceo_hrid']) == ceo_pw_before
