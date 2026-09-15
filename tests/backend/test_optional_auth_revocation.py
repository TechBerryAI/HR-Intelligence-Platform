"""Optional-auth routes must drop revoked/deactivated users to anonymous."""
from __future__ import annotations

import pytest

from live_db_helpers import (
    app_client,
    auth_header,
    login,
    seed_job,
    seed_org_with_staff,
)


def test_optional_auth_after_deactivate(app_client):
    org = seed_org_with_staff()
    job_id = seed_job(org['org_id'], org['recruiter_hrid'], title='Private Board Job')
    token = login(app_client, org['recruiter_email'])

    before = app_client.get(f'/api/jobs/{job_id}', headers=auth_header(token))
    assert before.status_code == 200

    head_token = login(app_client, org['head_email'])
    deact = app_client.delete(
        f"/api/head-hr/admins/{org['recruiter_hrid']}",
        headers=auth_header(head_token),
    )
    assert deact.status_code == 200

    after = app_client.get(f'/api/jobs/{job_id}', headers=auth_header(token))
    # Token no longer treated as staff → public path → 404 without ?company=
    assert after.status_code == 404
    assert after.get_json().get('error') in ('Job not found', 'Not found')


def test_optional_auth_after_session_revoke(app_client):
    org = seed_org_with_staff()
    job_id = seed_job(org['org_id'], org['recruiter_hrid'])
    token = login(app_client, org['recruiter_email'])
    assert app_client.get(f'/api/jobs/{job_id}', headers=auth_header(token)).status_code == 200

    from app.domains.identity.sessions.service import deactivate_all_user_sessions

    deactivate_all_user_sessions(org['recruiter_hrid'], 'HR')

    after = app_client.get(f'/api/jobs/{job_id}', headers=auth_header(token))
    assert after.status_code == 404
