"""Cross-tenant isolation probes for jobs, head-hr, applications, media."""
from __future__ import annotations

from live_db_helpers import app_client, auth_header, login, seed_job, seed_org_with_staff


def test_tenant_isolation_matrix(app_client):
    a = seed_org_with_staff()
    b = seed_org_with_staff()
    a_job = seed_job(a['org_id'], a['recruiter_hrid'], title='A Only')
    b_token = login(app_client, b['head_email'])
    headers = auth_header(b_token)

    # Staff list must not include other org jobs
    jobs_all = app_client.get('/api/jobs/all', headers=headers)
    assert jobs_all.status_code == 200
    ids = {(j.get('id') or j.get('jdid')) for j in (jobs_all.get_json() or [])}
    assert a_job not in ids

    # Job detail as other tenant → 404
    detail = app_client.get(f'/api/jobs/{a_job}', headers=headers)
    assert detail.status_code == 404

    # Head HR cannot mutate other-org recruiter
    cross = app_client.delete(
        f"/api/head-hr/admins/{a['recruiter_hrid']}",
        headers=headers,
    )
    assert cross.status_code == 404

    # Applications for foreign job denied or empty
    apps = app_client.get(f'/api/jobs/{a_job}/applications', headers=headers)
    assert apps.status_code in (200, 403, 404)
    if apps.status_code == 200:
        body = apps.get_json()
        rows = body if isinstance(body, list) else (body or {}).get('applications') or []
        assert rows == []

    # Media without auth denied
    media = app_client.get('/api/media/missing-key')
    assert media.status_code in (401, 403, 404)
