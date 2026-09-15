"""Head HR admin soft-deactivation against live PostgreSQL."""
from __future__ import annotations

from live_db_helpers import (
    app_client,
    auth_header,
    login,
    seed_job,
    seed_org_with_staff,
)


def test_deactivate_recruiter_without_jobs(app_client):
    org = seed_org_with_staff()
    token = login(app_client, org['head_email'])
    resp = app_client.delete(
        f"/api/head-hr/admins/{org['recruiter_hrid']}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.get_json()['account_status'] == 'deactivated'
    from app.database.connection.db import db_get

    row = db_get('SELECT account_status FROM hr_signup WHERE hrid = ?', (org['recruiter_hrid'],))
    assert row['account_status'] == 'deactivated'


def test_deactivate_recruiter_with_posted_jobs_preserves_jobs(app_client):
    org = seed_org_with_staff()
    job_id = seed_job(org['org_id'], org['recruiter_hrid'], title='Kept Job')
    token = login(app_client, org['head_email'])
    resp = app_client.delete(
        f"/api/head-hr/admins/{org['recruiter_hrid']}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200

    from app.database.connection.db import db_get, db_all

    job = db_get('SELECT jdid, posted_by, organization_id FROM jobs WHERE jdid = ?', (job_id,))
    assert job is not None
    assert job['posted_by'] == org['recruiter_hrid']
    assert str(job['organization_id']) == org['org_id']
    # Recruiter row still exists (soft-deactivate)
    admin = db_get('SELECT hrid FROM hr_signup WHERE hrid = ?', (org['recruiter_hrid'],))
    assert admin is not None
    # Job remains queryable for head HR
    head_token = login(app_client, org['head_email'])
    listed = app_client.get('/api/jobs/all', headers=auth_header(head_token))
    assert listed.status_code == 200
    ids = {(j.get('id') or j.get('jdid')) for j in (listed.get_json() or [])}
    assert job_id in ids


def test_deactivate_rejects_self(app_client):
    org = seed_org_with_staff()
    token = login(app_client, org['head_email'])
    resp = app_client.delete(
        f"/api/head-hr/admins/{org['head_hrid']}",
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_deactivate_rejects_ceo(app_client):
    org = seed_org_with_staff()
    token = login(app_client, org['head_email'])
    resp = app_client.delete(
        f"/api/head-hr/admins/{org['ceo_hrid']}",
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_deactivate_rejects_head_hr(app_client):
    org = seed_org_with_staff()
    token = login(app_client, org['head_email'])
    resp = app_client.delete(
        f"/api/head-hr/admins/{org['peer_hrid']}",
        headers=auth_header(token),
    )
    assert resp.status_code == 403


def test_deactivate_missing_admin_is_404(app_client):
    org = seed_org_with_staff()
    token = login(app_client, org['head_email'])
    resp = app_client.delete(
        '/api/head-hr/admins/HRID99999',
        headers=auth_header(token),
    )
    assert resp.status_code == 404


def test_deactivate_already_inactive_is_404(app_client):
    org = seed_org_with_staff()
    token = login(app_client, org['head_email'])
    first = app_client.delete(
        f"/api/head-hr/admins/{org['recruiter_hrid']}",
        headers=auth_header(token),
    )
    assert first.status_code == 200
    second = app_client.delete(
        f"/api/head-hr/admins/{org['recruiter_hrid']}",
        headers=auth_header(token),
    )
    assert second.status_code == 404
