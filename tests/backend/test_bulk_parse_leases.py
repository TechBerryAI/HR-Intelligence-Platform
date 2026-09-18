"""Regression: bulk parse file/session claims are CAS and multi-worker safe."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.domains.administration.repositories import bulk_session_db as bdb


def test_claim_file_for_processing_wins_once(monkeypatch):
    calls = {'n': 0}

    def fake_db_run(sql, params=None):
        calls['n'] += 1
        # First caller wins; second sees 0 changes
        return {'changes': 1 if calls['n'] == 1 else 0, 'lastID': None}

    monkeypatch.setattr(bdb, 'db_run', fake_db_run)
    assert bdb.claim_file_for_processing('f1', 'worker-a') is True
    assert bdb.claim_file_for_processing('f1', 'worker-b') is False


def test_claim_session_lease_rejects_active_lease(monkeypatch):
    def fake_db_run(sql, params=None):
        return {'changes': 0, 'lastID': None}

    monkeypatch.setattr(bdb, 'db_run', fake_db_run)
    assert bdb.claim_session_lease('s1', 'worker-b') is False


def test_claim_session_lease_allows_stale_recovery(monkeypatch):
    captured = {}

    def fake_db_run(sql, params=None):
        captured['sql'] = sql
        captured['params'] = params
        return {'changes': 1, 'lastID': None}

    monkeypatch.setattr(bdb, 'db_run', fake_db_run)
    assert bdb.claim_session_lease('s1', 'worker-c', total_files=3) is True
    sql = captured['sql']
    # Claim wins for Queued/Paused, or Running with expired/missing lease
    assert "status IN ('Queued', 'Paused')" in sql
    assert 'leased_until IS NULL OR leased_until < NOW()' in sql
    assert "status = 'Running'" in sql
    assert captured['params'][0] == 'worker-c'
    assert captured['params'][2] == 3
    assert captured['params'][3] == 's1'


def test_reclaim_stale_file_leases_returns_count(monkeypatch):
    monkeypatch.setattr(bdb, 'db_run', lambda *a, **k: {'changes': 4, 'lastID': None})
    assert bdb.reclaim_stale_file_leases() == 4


def test_start_staged_job_requires_session_claim(monkeypatch):
    from app.workers import bulk_parser as bp

    # Seed local job so start can proceed to claim
    with bp._local_jobs_lock:
        bp._local_jobs['job-x'] = {
            'status': 'pending',
            'staged_filenames': ['a.pdf'],
            'total_files': 1,
            'append': False,
            'started_by': 'HR001',
            'processed_files': 0,
            'failed_files': 0,
            'results': [],
            'message': '',
            'failed_filenames': [],
            'success_filenames': [],
            'failed_details': [],
            'started_at': None,
        }

    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.reclaim_stale_file_leases',
        lambda: 0,
    )
    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.list_queued_filenames',
        lambda sid: ['a.pdf'],
    )
    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.claim_session_lease',
        lambda *a, **k: False,
    )
    # Avoid actually writing staging dir checks failing — names come from DB
    ok, payload = bp.start_staged_job('job-x')
    assert ok is False
    assert 'another worker' in payload.get('error', '').lower()


def test_lease_until_is_in_future():
    until = bdb._lease_until(60)
    assert until > datetime.now(timezone.utc)
    assert until < datetime.now(timezone.utc) + timedelta(seconds=120)
