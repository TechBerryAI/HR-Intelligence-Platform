"""Per-tenant public job board with two organizations."""
from __future__ import annotations

from live_db_helpers import app_client, seed_job, seed_org_with_staff


def test_public_board_multitenant(app_client, monkeypatch):
    monkeypatch.delenv('DEFAULT_PUBLIC_COMPANY_SLUG', raising=False)
    alpha = seed_org_with_staff(name=f'Alpha Corp {__import__("uuid").uuid4().hex[:6]}')
    beta = seed_org_with_staff(name=f'Beta Corp {__import__("uuid").uuid4().hex[:6]}')
    a_job = seed_job(alpha['org_id'], alpha['recruiter_hrid'], title='Alpha Role')
    b_job = seed_job(beta['org_id'], beta['recruiter_hrid'], title='Beta Role')

    bare = app_client.get('/api/jobs/')
    assert bare.status_code == 404
    assert bare.get_json() == {'error': 'Not found'}
    assert 'hint' not in (bare.get_json() or {})

    alpha_list = app_client.get(f"/api/jobs/?company={alpha['org_slug']}")
    assert alpha_list.status_code == 200
    ids = {(j.get('id') or j.get('jdid')) for j in (alpha_list.get_json() or [])}
    assert a_job in ids
    assert b_job not in ids

    detail = app_client.get(f"/api/jobs/{a_job}?company={alpha['org_slug']}")
    assert detail.status_code == 200

    wrong = app_client.get(f"/api/jobs/{a_job}?company={beta['org_slug']}")
    assert wrong.status_code == 404
