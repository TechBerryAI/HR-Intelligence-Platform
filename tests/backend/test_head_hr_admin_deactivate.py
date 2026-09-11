"""Regression: Head HR admin soft-deactivation (no hard-delete FK crashes)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domains.administration.api import head_hr as head_hr_mod

ORG = '11111111-1111-1111-1111-111111111111'


@pytest.fixture
def capture_sql(monkeypatch):
    """Capture db_get / db_run calls; tests configure row responses."""
    state = {
        'get_rows': [],  # queue of return values for db_get
        'runs': [],
        'gets': [],
        'job_count': 0,
        'admin_row': None,
        'status_after': None,
    }

    def fake_get(sql, params=None):
        state['gets'].append((' '.join(sql.split()), params))
        sql_n = ' '.join(sql.split())
        if state['get_rows']:
            return state['get_rows'].pop(0)
        if 'FROM hr_signup' in sql_n and 'hrid = ?' in sql_n:
            return state['admin_row']
        if 'FROM jobs' in sql_n and 'posted_by' in sql_n:
            return {'cnt': state['job_count']}
        return None

    def fake_run(sql, params=None):
        sql_n = ' '.join(sql.split())
        state['runs'].append((sql_n, params))
        if 'UPDATE hr_signup' in sql_n and 'deactivated' in sql_n:
            state['status_after'] = 'deactivated'
            if state['admin_row'] is not None:
                state['admin_row'] = {**state['admin_row'], 'account_status': 'deactivated'}

    monkeypatch.setattr(head_hr_mod, 'db_get', fake_get)
    monkeypatch.setattr(head_hr_mod, 'db_run', fake_run)
    monkeypatch.setattr(
        'app.domains.identity.sessions.service.deactivate_all_user_sessions',
        lambda *_a, **_k: {'success': True},
    )
    return state


def test_deactivate_recruiter_without_jobs(capture_sql):
    capture_sql['admin_row'] = {
        'hrid': 'HRID010',
        'role': 'RECRUITER',
        'account_status': 'active',
    }
    capture_sql['job_count'] = 0
    body, status = head_hr_mod.deactivate_admin_account('HRID010', ORG, 'HRID001')
    assert status == 200
    assert body['account_status'] == 'deactivated'
    assert capture_sql['status_after'] == 'deactivated'
    assert not any('DELETE FROM hr_signup' in sql for sql, _ in capture_sql['runs'])
    assert any('account_status = \'deactivated\'' in sql for sql, _ in capture_sql['runs'])


def test_deactivate_recruiter_with_posted_jobs_preserves_jobs(capture_sql):
    capture_sql['admin_row'] = {
        'hrid': 'HRID011',
        'role': 'RECRUITER',
        'account_status': 'active',
    }
    capture_sql['job_count'] = 3
    jobs_before = capture_sql['job_count']

    body, status = head_hr_mod.deactivate_admin_account('HRID011', ORG, 'HRID001')
    assert status == 200
    assert body.get('hrid') == 'HRID011'
    assert capture_sql['job_count'] == jobs_before
    assert not any('DELETE FROM jobs' in sql for sql, _ in capture_sql['runs'])
    assert not any('DELETE FROM hr_signup' in sql for sql, _ in capture_sql['runs'])
    assert any(
        params == ('HRID011', ORG) and 'deactivated' in sql
        for sql, params in capture_sql['runs']
    )


def test_deactivate_rejects_self(capture_sql):
    capture_sql['admin_row'] = {
        'hrid': 'HRID001',
        'role': 'HEAD_HR',
        'account_status': 'active',
    }
    body, status = head_hr_mod.deactivate_admin_account('HRID001', ORG, 'HRID001')
    assert status == 403
    assert 'own account' in body['error']
    assert capture_sql['runs'] == []


def test_deactivate_rejects_ceo(capture_sql):
    capture_sql['admin_row'] = {
        'hrid': 'HRID002',
        'role': 'CEO',
        'account_status': 'active',
    }
    body, status = head_hr_mod.deactivate_admin_account('HRID002', ORG, 'HRID001')
    assert status == 403
    assert 'CEO' in body['error']
    assert capture_sql['runs'] == []


def test_deactivate_rejects_head_hr(capture_sql):
    capture_sql['admin_row'] = {
        'hrid': 'HRID003',
        'role': 'HEAD_HR',
        'account_status': 'active',
    }
    body, status = head_hr_mod.deactivate_admin_account('HRID003', ORG, 'HRID001')
    assert status == 403
    assert 'Head HR' in body['error']
    assert capture_sql['runs'] == []


def test_deactivate_missing_admin_is_404(capture_sql):
    capture_sql['admin_row'] = None
    body, status = head_hr_mod.deactivate_admin_account('HRID999', ORG, 'HRID001')
    assert status == 404
    assert body['error'] == 'Admin not found'
    assert capture_sql['runs'] == []


def test_deactivate_already_inactive_is_404(capture_sql):
    # Query filters active only — deactivated rows look like "not found"
    capture_sql['admin_row'] = None
    body, status = head_hr_mod.deactivate_admin_account('HRID010', ORG, 'HRID001')
    assert status == 404
    assert capture_sql['runs'] == []
