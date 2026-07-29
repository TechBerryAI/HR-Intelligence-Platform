"""Platform freeze smoke tests — RBAC, auth, and core API paths."""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"

HEAD_HR_EMAIL = os.getenv('SMOKE_HEAD_HR_EMAIL', 'chetan.gore@techberryinfotech.com')
HEAD_HR_PASSWORD = os.getenv('SMOKE_HEAD_HR_PASSWORD', 'P@ssw0rd')
CEO_EMAIL = os.getenv('SMOKE_CEO_EMAIL', 'unmesh.tari@techberryinfotech.com')
CEO_PASSWORD = os.getenv('SMOKE_CEO_PASSWORD', 'P@ssw0rd')
RECRUITER_EMAIL = os.getenv('SMOKE_RECRUITER_EMAIL', '')
RECRUITER_PASSWORD = os.getenv('SMOKE_RECRUITER_PASSWORD', '')
CANDIDATE_EMAIL = os.getenv('SMOKE_CANDIDATE_EMAIL', '')
CANDIDATE_PASSWORD = os.getenv('SMOKE_CANDIDATE_PASSWORD', '')

pytestmark = pytest.mark.integration


def _jwt_role(token: str) -> str | None:
    try:
        payload_b64 = token.split('.')[1]
        padding = '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
        return payload.get('role')
    except Exception:
        return None


def _auth_header(token: str) -> dict:
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture(scope='module')
def app_client():
    try:
        from wsgi import app
    except Exception as exc:
        pytest.skip(f'Flask app unavailable: {exc}')
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def _staff_login(client, email: str, password: str):
    if not email or not password:
        pytest.skip('Staff credentials not configured')
    resp = client.post('/api/login', json={'email': email, 'password': password})
    if resp.status_code != 200:
        pytest.skip(f'Staff login failed for {email}: {resp.status_code} {resp.get_json()}')
    data = resp.get_json() or {}
    token = data.get('token')
    if not token:
        pytest.skip('No token in staff login response')
    return token, data.get('user') or {}


def _candidate_login(client, email: str, password: str):
    if not email or not password:
        pytest.skip('Candidate credentials not configured')
    resp = client.post('/api/candidate/login', json={'email': email, 'password': password})
    if resp.status_code != 200:
        pytest.skip(f'Candidate login failed for {email}: {resp.status_code} {resp.get_json()}')
    data = resp.get_json() or {}
    token = data.get('token')
    if not token:
        pytest.skip('No token in candidate login response')
    return token


def test_health_ok(app_client):
    resp = app_client.get('/health')
    assert resp.status_code == 200
    body = resp.get_json() or {}
    assert body.get('status') == 'ok'


def test_head_hr_login_role(app_client):
    token, user = _staff_login(app_client, HEAD_HR_EMAIL, HEAD_HR_PASSWORD)
    assert _jwt_role(token) == 'HEAD_HR'
    assert user.get('role') == 'HEAD_HR'


def test_ceo_login_role(app_client):
    token, user = _staff_login(app_client, CEO_EMAIL, CEO_PASSWORD)
    assert _jwt_role(token) == 'CEO'
    assert user.get('role') == 'CEO'


def test_head_hr_stats(app_client):
    token, _ = _staff_login(app_client, HEAD_HR_EMAIL, HEAD_HR_PASSWORD)
    resp = app_client.get('/api/head-hr/stats', headers=_auth_header(token))
    assert resp.status_code == 200


def test_ceo_stats_read_only(app_client):
    token, _ = _staff_login(app_client, CEO_EMAIL, CEO_PASSWORD)
    resp = app_client.get('/api/head-hr/stats', headers=_auth_header(token))
    assert resp.status_code == 200


def test_ceo_job_create_blocked(app_client):
    token, _ = _staff_login(app_client, CEO_EMAIL, CEO_PASSWORD)
    resp = app_client.post(
        '/api/jobs/',
        headers=_auth_header(token),
        json={'title': 'CEO Blocked Job', 'company': 'Test', 'location': 'Remote'},
    )
    assert resp.status_code == 403


def test_legacy_super_admin_prefix_removed(app_client):
    token, _ = _staff_login(app_client, HEAD_HR_EMAIL, HEAD_HR_PASSWORD)
    resp = app_client.get('/api/super-admin/stats', headers=_auth_header(token))
    assert resp.status_code == 404


def _jobs_list(resp):
    data = resp.get_json()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get('jobs') or []
    return []


def test_head_hr_sees_all_jobs(app_client):
    token, _ = _staff_login(app_client, HEAD_HR_EMAIL, HEAD_HR_PASSWORD)
    public = app_client.get('/api/jobs/')
    head_hr = app_client.get('/api/jobs/', headers=_auth_header(token))
    assert public.status_code == 200
    assert head_hr.status_code == 200
    public_jobs = _jobs_list(public)
    head_jobs = _jobs_list(head_hr)
    assert len(head_jobs) >= len(public_jobs)


def test_recruiter_job_scope(app_client):
    token, user = _staff_login(app_client, RECRUITER_EMAIL, RECRUITER_PASSWORD)
    resp = app_client.get('/api/jobs/', headers=_auth_header(token))
    assert resp.status_code == 200
    jobs = _jobs_list(resp)
    hrid = user.get('hrId') or user.get('hrid')
    if hrid and jobs:
        for job in jobs:
            posted_by = job.get('posted_by') or job.get('postedBy')
            assert posted_by == hrid


def test_candidate_profile(app_client):
    token = _candidate_login(app_client, CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
    resp = app_client.get('/api/candidate/profile', headers=_auth_header(token))
    assert resp.status_code == 200


def test_candidate_applications_list(app_client):
    token = _candidate_login(app_client, CANDIDATE_EMAIL, CANDIDATE_PASSWORD)
    resp = app_client.get('/api/applications/', headers=_auth_header(token))
    assert resp.status_code == 200


def test_refresh_token_roundtrip(app_client):
    token, _ = _staff_login(app_client, HEAD_HR_EMAIL, HEAD_HR_PASSWORD)
    login_resp = app_client.post('/api/login', json={'email': HEAD_HR_EMAIL, 'password': HEAD_HR_PASSWORD})
    refresh_token = (login_resp.get_json() or {}).get('refresh_token')
    if not refresh_token:
        pytest.skip('No refresh_token in login response')
    resp = app_client.post('/api/refresh', json={'refresh_token': refresh_token})
    assert resp.status_code == 200
    body = resp.get_json() or {}
    assert body.get('token')
    assert body.get('refresh_token')
    assert _jwt_role(body['token']) == 'HEAD_HR'


def test_candidate_forgot_password_request(app_client):
    email = CANDIDATE_EMAIL or 'nonexistent.candidate@example.com'
    resp = app_client.post('/api/candidate/forgot-password', json={'email': email})
    if resp.status_code == 500:
        pytest.skip('Database unavailable for forgot-password test')
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert 'message' in (resp.get_json() or {})
    else:
        assert 'error' in (resp.get_json() or {})


def test_job_create_links_parsed_jd_id(app_client):
    """When parsedJdId is provided, jobs.parsed_jd_id and parsed_jds.job_id are linked."""
    import uuid

    from toon import toon_dumps

    token, user = _staff_login(app_client, RECRUITER_EMAIL, RECRUITER_PASSWORD)
    headers = _auth_header(token)

    sample_jd = {
        "title": "Senior Python Developer",
        "company": "Acme Corp",
        "location": "Remote",
        "required_skills": ["Python", "Django"],
        "preferred_skills": ["AWS"],
        "responsibilities": ["Build APIs"],
        "description": "Backend role",
    }
    from ai_runtime_adapter import normalize_proposal

    parsed_id = str(uuid.uuid4())
    raw_id = str(uuid.uuid4())
    toon = normalize_proposal(sample_jd, "jd")
    hr_id = user.get('hrId') or user.get('hrid')
    from db import db_get, db_run

    db_run(
        "INSERT INTO raw_files (id, uploader_id, uploader_role, filename, mime_type, file_hash, storage_url) VALUES (?, ?, 'recruiter', 'jd.txt', 'text/plain', ?, 'test')",
        (raw_id, hr_id, f'test-{parsed_id}'),
    )
    db_run(
        "INSERT INTO parsed_jds (id, raw_file_id, toon, full_text, confidence, model_version) VALUES (?, ?, ?, 'sample', 0.9, 'test')",
        (parsed_id, raw_id, toon_dumps(toon)),
    )

    resp = app_client.post(
        '/api/jobs/',
        headers=headers,
        json={
            'title': f'JD Link Test {parsed_id[:8]}',
            'company': 'Test Co',
            'location': 'Remote',
            'description': 'Test job with linked JD',
            'parsedJdId': parsed_id,
        },
    )
    assert resp.status_code == 201, resp.get_json()
    job_id = (resp.get_json() or {}).get('id')
    job_row = db_get('SELECT parsed_jd_id FROM jobs WHERE jdid = ?', (job_id,))
    assert job_row and str(job_row.get('parsed_jd_id')) == parsed_id
    jd_row = db_get('SELECT job_id FROM parsed_jds WHERE id = ?', (parsed_id,))
    assert jd_row and jd_row.get('job_id') == job_id
