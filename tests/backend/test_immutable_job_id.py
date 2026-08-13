"""Regression: jobs.jdid is immutable after create (FK integrity)."""
from __future__ import annotations

import inspect

from app.domains.recruitment.api import jobs as jobs_mod


def test_update_job_source_never_mutates_jdid():
    src = inspect.getsource(jobs_mod.update_job)
    assert 'should_regenerate_jdid' not in src
    assert 'generate_jdid_from_title' not in src
    assert 'UPDATE applications SET job_id' not in src
    assert 'UPDATE matches SET job_id' not in src
    # Must update content fields keyed by existing jdid, not rewrite PK.
    assert 'WHERE jdid = ?' in src
    assert 'jdid = ?,' not in src.replace('WHERE jdid = ?', '')


def test_update_job_preserves_jdid_and_application_fk(monkeypatch):
    """Simulate edit with dependents: jdid stays; applications still point at same job."""
    calls = []
    job = {
        'jdid': 'DA001',
        'title': 'Data Analyst',
        'location': 'Remote',
        'salary': '100000',
        'experience': '2-4 years',
        'description': 'Old',
        'keywords': None,
        'organization_id': 'org-1',
        'posted_by': 'HR001',
        'enabled': True,
    }
    updated = {**job, 'title': 'Senior Data Analyst', 'description': 'New'}

    def fake_get_job(job_id, user, require_write=False):
        assert job_id == 'DA001'
        return job

    def fake_db_run(sql, params=None):
        calls.append(('run', sql.strip(), params))

    def fake_db_get(sql, params=None):
        calls.append(('get', sql.strip(), params))
        if 'FROM jobs WHERE jdid' in sql:
            return updated
        return None

    monkeypatch.setattr(jobs_mod, '_get_job_for_user', fake_get_job)
    monkeypatch.setattr(jobs_mod, 'db_run', fake_db_run)
    monkeypatch.setattr(jobs_mod, 'db_get', fake_db_get)
    monkeypatch.setattr(jobs_mod, 'emit_job_updated', lambda *a, **k: None)
    monkeypatch.setattr(jobs_mod, '_serialize_job', lambda j: {'id': j['jdid'], 'title': j['title']})

    from flask import Flask

    app = Flask(__name__)
    app.register_blueprint(jobs_mod.jobs_bp, url_prefix='/api/jobs')

    with app.test_request_context(
        '/api/jobs/DA001',
        method='PUT',
        json={
            'title': 'Senior Data Analyst',
            'location': 'Remote',
            'salary': '120000',
            'experience': '3-5 years',
            'description': 'New',
        },
    ):
        from flask import request as flask_request

        flask_request.user = {
            'hrid': 'HR001',
            'role': 'RECRUITER',
            'organization_id': 'org-1',
        }
        # Bypass auth decorators by calling underlying function if wrapped
        fn = jobs_mod.update_job
        while hasattr(fn, '__wrapped__'):
            fn = fn.__wrapped__
        resp = fn('DA001')

    assert resp[1] == 200 if isinstance(resp, tuple) else resp.status_code == 200
    update_sqls = [c for c in calls if c[0] == 'run']
    assert len(update_sqls) == 1
    sql, params = update_sqls[0][1], update_sqls[0][2]
    assert 'jdid = ?' not in sql.split('WHERE')[0]  # SET clause must not change jdid
    assert params[-1] == 'DA001'
    # No child FK rewrites
    assert not any('UPDATE applications' in c[1] for c in calls)
    assert not any('UPDATE matches' in c[1] for c in calls)


def test_generate_jdid_still_exists_for_create():
    assert callable(jobs_mod.generate_jdid_from_title)
