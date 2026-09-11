"""Account lifecycle: create → deactivate → list inactive → reactivate → login."""
from __future__ import annotations

from live_db_helpers import (
    STRONG_PASSWORD,
    app_client,
    auth_header,
    login,
    seed_org_with_staff,
    unique_email,
)


def test_account_lifecycle_reactivate(app_client):
    org = seed_org_with_staff()
    head = login(app_client, org['head_email'])
    email = unique_email()

    create = app_client.post(
        '/api/head-hr/admins',
        headers=auth_header(head),
        json={'email': email, 'fullName': 'Lifecycle Rec', 'password': STRONG_PASSWORD},
    )
    assert create.status_code == 201, create.get_json()
    hrid = create.get_json()['admin']['hrid']

    deact = app_client.delete(f'/api/head-hr/admins/{hrid}', headers=auth_header(head))
    assert deact.status_code == 200

    listed = app_client.get(
        '/api/head-hr/admins?include_inactive=true',
        headers=auth_header(head),
    )
    assert listed.status_code == 200
    admins = listed.get_json()['admins']
    match = next(a for a in admins if a['hrid'] == hrid)
    assert match['account_status'] == 'deactivated'

    # Recreate with same email must point at reactivate
    again = app_client.post(
        '/api/head-hr/admins',
        headers=auth_header(head),
        json={'email': email, 'fullName': 'Lifecycle Rec', 'password': STRONG_PASSWORD},
    )
    assert again.status_code == 400
    err = (again.get_json().get('error') or '').lower()
    assert 'reactivate' in err

    react = app_client.post(
        f'/api/head-hr/admins/{hrid}/reactivate',
        headers=auth_header(head),
    )
    assert react.status_code == 200
    assert react.get_json()['account_status'] == 'active'

    token = login(app_client, email)
    assert token
