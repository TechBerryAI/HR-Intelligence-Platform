"""Parametrized HTTP coverage for registered Flask routes (auth + smoke)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PUBLIC_ROUTES: set[tuple[str, str]] = {
    ('GET', '/'),
    ('GET', '/health'),
    ('GET', '/ready'),
    ('GET', '/api/jobs/'),
    ('GET', '/api/jobs/all'),
    ('GET', '/api/companies/'),
    ('GET', '/api/media/public/hero-video'),
    ('GET', '/api/media/health'),
    ('POST', '/api/login'),
    ('POST', '/api/parse/resume/public'),
    ('POST', '/api/parse/resume/public/stream'),
    ('POST', '/api/parse/timing-client'),
    ('POST', '/api/jobs/<string:job_id>/apply'),
    ('GET', '/api/interviews/book/<string:token>'),
    ('POST', '/api/interviews/book/<string:token>'),
    ('POST', '/api/support/submit'),
    ('POST', '/api/feedback/submit'),
    ('POST', '/api/applications/ats/result'),
    ('GET', '/api/integrations/calendar/google/callback'),
    ('GET', '/api/integrations/google/callback'),
}

PROTECTED_PREFIXES = (
    '/api/head-hr',
    '/api/admin',
    '/api/sessions',
    '/api/parse/resume',
    '/api/parse/jd',
    '/api/integrations',
    '/api/jobs/<string:job_id>/applications',
    '/api/candidate',
    '/api/feedback/list',
    '/api/support/all',
    '/api/support/my-requests',
    '/api/change-password',
)


def _route_is_protected(method: str, rule: str) -> bool:
    if method == 'OPTIONS':
        return False
    if (method, rule) in PUBLIC_ROUTES:
        return False
    if rule.startswith('/api/login') or rule.startswith('/api/signup'):
        return False
    if rule.startswith('/api/forgot-password') or rule.startswith('/api/reset-password'):
        return False
    if rule.startswith('/api/verify-otp') or rule.startswith('/api/resend-otp'):
        return False
    if rule.startswith('/api/refresh'):
        return False
    if rule == '/api/logout':
        return False  # idempotent no-op without tokens (see test_logout_idempotent_without_auth)
    for prefix in PROTECTED_PREFIXES:
        if rule == prefix or rule.startswith(prefix.rstrip('/') + '/') or rule.startswith(prefix):
            return True
    if method in ('POST', 'PUT', 'PATCH', 'DELETE') and rule.startswith('/api/jobs'):
        if rule.endswith('/apply'):
            return False
        return True
    if rule.startswith('/api/parsed/'):
        return True
    if rule.startswith('/api/parse/jobs/'):
        return False
    return False


def _sample_path(rule: str) -> str:
    out = rule
    replacements = {
        '<string:job_id>': '00000000-0000-0000-0000-000000000001',
        '<string:jdid>': '00000000-0000-0000-0000-000000000001',
        '<string:candidate_id>': '00000000-0000-0000-0000-000000000001',
        '<string:cid>': '00000000-0000-0000-0000-000000000001',
        '<string:token>': 'invalid-token-smoke',
        '<string:provider>': 'naukri',
        '<string:provider_or_id>': 'naukri',
        '<int:feedback_id>': '1',
        '<int:request_id>': '1',
        '<int:app_id>': '1',
        '<int:application_id>': '1',
        '<int:external_job_id>': '1',
        '<path:request_id>': 'smoke-req-id',
        '<hrid>': '00000000-0000-0000-0000-000000000001',
        '<parsed_id>': '00000000-0000-0000-0000-000000000001',
        '<cid>': '00000000-0000-0000-0000-000000000001',
        '<jdid>': '00000000-0000-0000-0000-000000000001',
        '<job_id>': '00000000-0000-0000-0000-000000000001',
    }
    for token, value in replacements.items():
        out = out.replace(token, value)
    return out


def _collect_routes(app) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        methods = sorted(m for m in rule.methods if m not in ('HEAD',))
        for method in methods:
            rules.append((method, rule.rule))
    return sorted(set(rules))


@pytest.fixture(scope='module')
def app_client():
    try:
        from wsgi import app
    except Exception as exc:
        pytest.skip(f'Flask app unavailable: {exc}')
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(scope='module')
def route_manifest(app_client):
    return _collect_routes(app_client.application)


def test_route_manifest_nonempty(route_manifest):
    assert len(route_manifest) >= 100, len(route_manifest)


def test_all_protected_routes_reject_without_auth(app_client, route_manifest):
    """Every non-public route must not succeed anonymously."""
    failures: list[str] = []
    protected = [(m, r) for m, r in route_manifest if _route_is_protected(m, r)]
    assert protected, 'No protected routes classified'
    for method, rule in protected:
        path = _sample_path(rule)
        resp = app_client.open(path, method=method)
        if resp.status_code in (200, 201, 202):
            failures.append(f'{method} {path} => {resp.status_code} (expected auth failure)')
    assert not failures, '\n'.join(failures[:20])


def test_logout_idempotent_without_auth(app_client):
    """Logout is intentionally idempotent when no session token is supplied."""
    resp = app_client.post('/api/logout')
    assert resp.status_code == 200


def test_public_health_and_jobs(app_client):
    assert app_client.get('/health').status_code == 200
    assert app_client.get('/ready').status_code == 200
    # Multi-tenant: bare public board resolves only via ?company= or DEFAULT_PUBLIC_COMPANY_SLUG
    from live_db_helpers import seed_job, seed_org_with_staff
    import os

    os.environ.pop('DEFAULT_PUBLIC_COMPANY_SLUG', None)
    alpha = seed_org_with_staff(name=f'Alpha Board {__import__("uuid").uuid4().hex[:6]}')
    _beta = seed_org_with_staff(name=f'Beta Board {__import__("uuid").uuid4().hex[:6]}')
    seed_job(alpha['org_id'], alpha['recruiter_hrid'], title='Alpha Public')

    bare = app_client.get('/api/jobs/')
    assert bare.status_code == 404
    assert 'hint' not in (bare.get_json() or {})

    listed = app_client.get(f"/api/jobs/?company={alpha['org_slug']}")
    assert listed.status_code == 200
    assert isinstance(listed.get_json(), list)


def test_invalid_jwt_rejected(app_client):
    headers = {'Authorization': 'Bearer not-a-valid-jwt'}
    resp = app_client.get('/api/head-hr/stats', headers=headers)
    assert resp.status_code in (401, 403)


def test_sql_injection_in_public_apply_validation(app_client):
    from live_db_helpers import seed_job, seed_org_with_staff

    org = seed_org_with_staff()
    job_id = seed_job(org['org_id'], org['recruiter_hrid'], title='Apply Probe')
    jobs = app_client.get(f"/api/jobs/?company={org['org_slug']}").get_json()
    job_list = jobs if isinstance(jobs, list) else (jobs or {}).get('jobs') or []
    assert job_list, 'expected seeded public jobs'
    job_id = job_list[0].get('id') or job_list[0].get('jdid') or job_id
    resp = app_client.post(
        f'/api/jobs/{job_id}/apply',
        data={
            'fullName': "'; DROP TABLE candidates; --",
            'email': 'not-an-email',
        },
    )
    assert resp.status_code == 400
    body = resp.get_data(as_text=True).lower()
    assert 'drop table' not in body


def test_idor_fake_candidate_resume_denied_without_auth(app_client):
    resp = app_client.get(
        '/api/head-hr/candidates/00000000-0000-0000-0000-000000000099/resume',
    )
    assert resp.status_code in (401, 403, 404)


def test_parse_public_requires_file(app_client):
    resp = app_client.post('/api/parse/resume/public')
    assert resp.status_code == 400


def test_ceo_cannot_create_job_when_authed(app_client):
    from live_db_helpers import auth_header, login, seed_org_with_staff

    org = seed_org_with_staff()
    token = login(app_client, org['ceo_email'])
    resp = app_client.post(
        '/api/jobs/',
        headers=auth_header(token),
        json={'title': 'QA blocked job', 'company': 'Test', 'location': 'Remote'},
    )
    assert resp.status_code == 403


def test_head_hr_stats_when_authed(app_client):
    from live_db_helpers import auth_header, login, seed_org_with_staff

    org = seed_org_with_staff()
    token = login(app_client, org['head_email'])
    resp = app_client.get(
        '/api/head-hr/stats',
        headers=auth_header(token),
    )
    assert resp.status_code == 200
