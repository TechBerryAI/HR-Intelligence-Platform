"""PostgreSQL integration tests for durable external_jobs outbox."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.domains.integrations import repository as repo
from app.domains.integrations.service import publish_service
from app.domains.integrations.worker import outbox as outbox_mod


def _db_ok() -> bool:
    try:
        from app.database.connection.db import db_get

        return bool(db_get('SELECT 1 AS ok'))
    except Exception:
        return False


@pytest.fixture
def pg():
    if not _db_ok():
        pytest.skip('Postgres unavailable')
    # Ensure outbox columns exist
    from app.database.connection.db import db_get

    col = db_get(
        """
        SELECT 1 AS ok FROM information_schema.columns
        WHERE table_name='external_jobs' AND column_name='leased_until'
        """
    )
    if not col:
        pytest.skip('external_jobs outbox columns missing — run alembic upgrade')
    yield


def _unique_job() -> str:
    return f'OUTBOX{uuid.uuid4().hex[:8].upper()}'


def _cleanup(job_id: str):
    from app.database.connection.db import db_run

    db_run('DELETE FROM sync_logs WHERE job_id = ?', (job_id,))
    db_run('DELETE FROM external_jobs WHERE job_id = ?', (job_id,))


def _force_expire_lease(external_row_id: int) -> None:
    """Expire using Postgres NOW() — same clock as claim_pending_external_jobs."""
    from app.database.connection.db import db_run

    db_run(
        "UPDATE external_jobs SET leased_until = NOW() - INTERVAL '1 second' WHERE id = ?",
        (external_row_id,),
    )


def _reclaim_expired_row(
    *,
    external_row_id: int,
    job_id: str,
    worker_id: str,
    timeout: float = 5.0,
) -> dict:
    """Wait until the row is reclaimable, then claim it (retries SKIP LOCKED contention)."""
    import time

    from app.database.connection.db import db_get

    deadline = time.monotonic() + timeout
    last_diag = None
    while time.monotonic() < deadline:
        last_diag = db_get(
            """
            SELECT id, sync_status, leased_by, leased_until,
                   (leased_until IS NULL OR leased_until < NOW()) AS reclaimable,
                   COALESCE(next_attempt_at, TIMESTAMPTZ '-infinity') <= NOW() AS due
            FROM external_jobs
            WHERE id = ?
            """,
            (external_row_id,),
        )
        if not last_diag:
            raise AssertionError(f'external_jobs row {external_row_id} missing')
        if last_diag.get('sync_status') != 'pending':
            raise AssertionError(
                f'row {external_row_id} no longer pending before reclaim: {last_diag!r}'
            )
        if last_diag.get('reclaimable') and last_diag.get('due'):
            for row in repo.claim_pending_external_jobs(worker_id, limit=10, job_id=job_id):
                if row['id'] == external_row_id and row.get('leased_by') == worker_id:
                    return row
        time.sleep(0.02)
    raise AssertionError(
        f'{worker_id!r} could not reclaim row {external_row_id}; last_state={last_diag!r}'
    )
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    monkeypatch.setattr(
        publish_service,
        '_best_effort_memory_hint',
        lambda task: None,
    )
    monkeypatch.setattr(
        repo,
        'list_enabled_providers',
        lambda ck: [{'provider': 'linkedin'}],
    )
    try:
        result = publish_service.enqueue_publish(company, job_id, providers=['linkedin'])
        assert result['durable'] is True
        row = repo.get_external_job(job_id, 'linkedin')
        assert row is not None
        assert row['sync_status'] == 'pending'
        assert row.get('pending_operation') in ('publish', 'update')
        assert row.get('next_attempt_at') is not None
    finally:
        _cleanup(job_id)


def test_enqueue_close_persists_durable_pending(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    monkeypatch.setattr(publish_service, '_best_effort_memory_hint', lambda t: None)
    try:
        repo.upsert_external_job(
            company,
            job_id,
            'naukri',
            external_job_id='NK-1',
            sync_status='published',
            mark_published=True,
        )
        result = publish_service.enqueue_close(company, job_id, providers=['naukri'])
        assert result['durable'] is True
        row = repo.get_external_job(job_id, 'naukri')
        assert row['sync_status'] == 'pending'
        assert row['pending_operation'] == 'close'
        assert row.get('external_job_id') == 'NK-1'
    finally:
        _cleanup(job_id)


def test_claim_exactly_once_two_workers(pg):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    try:
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
        )
        a = repo.claim_pending_external_jobs('worker-A', limit=10, job_id=job_id)
        claimed_ids = {r['id'] for r in a if r['job_id'] == job_id}
        assert len(claimed_ids) == 1
        b = repo.claim_pending_external_jobs('worker-B', limit=10, job_id=job_id)
        b_ids = {r['id'] for r in b if r['job_id'] == job_id}
        assert b_ids == set()
    finally:
        _cleanup(job_id)


def test_expired_lease_reclaimed_by_other_worker(pg):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'

    try:
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
        )
        a = repo.claim_pending_external_jobs('worker-A', limit=50, job_id=job_id)
        matches = [r for r in a if r['job_id'] == job_id]
        assert len(matches) == 1, f'worker-A expected one row, got {a!r}'
        row = matches[0]
        assert row.get('leased_by') == 'worker-A'
        _force_expire_lease(row['id'])
        reclaimed = _reclaim_expired_row(
            external_row_id=row['id'],
            job_id=job_id,
            worker_id='worker-B',
        )
        assert reclaimed.get('leased_by') == 'worker-B'
    finally:
        _cleanup(job_id)


def test_failed_task_retries_with_next_attempt(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'

    class FailResult:
        success = False
        provider = 'linkedin'
        error = 'boom'
        external_job_id = None
        external_status = None

        def to_dict(self):
            return {'success': False, 'error': 'boom'}

    class Agg:
        results = [FailResult()]

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.publish_job',
        lambda self, *a, **k: Agg(),
    )
    monkeypatch.setattr(
        'app.domains.integrations.service.publish_service.load_job_snapshot',
        lambda *a, **k: MagicMock(job_id=job_id, company_key=company, to_dict=lambda: {}),
    )
    monkeypatch.setattr(
        'app.domains.integrations.config.get_max_retries',
        lambda: 3,
    )

    try:
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
            retry_count=0,
        )
        claimed = repo.claim_pending_external_jobs('worker-R', limit=50, job_id=job_id)
        row = next(r for r in claimed if r['job_id'] == job_id)
        outbox_mod.process_external_job_row(row)
        after = repo.get_external_job(job_id, 'linkedin')
        assert after['sync_status'] == 'pending'
        assert int(after['retry_count']) == 1
        assert after.get('next_attempt_at') is not None
        assert after.get('leased_by') is None
    finally:
        _cleanup(job_id)


def test_retry_limit_marks_dead(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'

    class FailResult:
        success = False
        provider = 'linkedin'
        error = 'still boom'
        external_job_id = None
        external_status = None

        def to_dict(self):
            return {'success': False}

    class Agg:
        results = [FailResult()]

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.publish_job',
        lambda self, *a, **k: Agg(),
    )
    monkeypatch.setattr(
        'app.domains.integrations.service.publish_service.load_job_snapshot',
        lambda *a, **k: MagicMock(job_id=job_id, company_key=company, to_dict=lambda: {}),
    )
    monkeypatch.setattr(
        'app.domains.integrations.worker.retry.get_max_retries',
        lambda: 1,
    )

    try:
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
            retry_count=1,  # already at max-1; next failure → dead when max=1 means should_retry(1) is False
        )
        # should_retry(retry_count) with next_retry-1: next_retry=2, should_retry(1) → 1 < 1 False
        claimed = repo.claim_pending_external_jobs('worker-D', limit=50, job_id=job_id)
        row = next(r for r in claimed if r['job_id'] == job_id)
        outbox_mod.process_external_job_row(row)
        after = repo.get_external_job(job_id, 'linkedin')
        assert after['sync_status'] == 'dead'
    finally:
        _cleanup(job_id)


def test_publish_success_persists_completed(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'

    class OkResult:
        success = True
        provider = 'linkedin'
        error = None
        external_job_id = 'LI-EXT-1'
        external_status = 'active'

        def to_dict(self):
            return {'success': True, 'external_job_id': 'LI-EXT-1'}

    class Agg:
        results = [OkResult()]

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.publish_job',
        lambda self, snapshot, **k: (
            repo.upsert_external_job(
                company,
                job_id,
                'linkedin',
                external_job_id='LI-EXT-1',
                sync_status='published',
                mark_published=True,
                clear_lease=True,
            )
            or Agg()
        )
        or Agg(),
    )
    # Simpler: patch process to call persist like manager would
    monkeypatch.setattr(
        'app.domains.integrations.service.publish_service.load_job_snapshot',
        lambda *a, **k: MagicMock(job_id=job_id, company_key=company, to_dict=lambda: {}),
    )

    def fake_publish(self, snapshot, **kwargs):
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            external_job_id='LI-EXT-1',
            sync_status='published',
            mark_published=True,
            clear_lease=True,
        )
        return Agg()

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.publish_job',
        fake_publish,
    )

    try:
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
        )
        claimed = repo.claim_pending_external_jobs('worker-S', limit=50, job_id=job_id)
        row = next(r for r in claimed if r['job_id'] == job_id)
        outbox_mod.process_external_job_row(row)
        after = repo.get_external_job(job_id, 'linkedin')
        assert after['sync_status'] == 'published'
        assert after['external_job_id'] == 'LI-EXT-1'
        assert after.get('leased_by') is None
    finally:
        _cleanup(job_id)


def test_close_success_persists_closed(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'

    class OkResult:
        success = True
        provider = 'naukri'
        error = None
        external_job_id = 'NK-9'
        external_status = 'closed'

        def to_dict(self):
            return {'success': True}

    class Agg:
        results = [OkResult()]

    def fake_close(self, company_key, jid, **kwargs):
        repo.upsert_external_job(
            company_key,
            jid,
            'naukri',
            external_job_id='NK-9',
            sync_status='closed',
            clear_lease=True,
        )
        return Agg()

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.close_job',
        fake_close,
    )
    try:
        repo.upsert_external_job(
            company,
            job_id,
            'naukri',
            external_job_id='NK-9',
            sync_status='pending',
            pending_operation='close',
            due_now=True,
            clear_lease=True,
        )
        claimed = repo.claim_pending_external_jobs('worker-C', limit=50, job_id=job_id)
        row = next(r for r in claimed if r['job_id'] == job_id)
        outbox_mod.process_external_job_row(row)
        after = repo.get_external_job(job_id, 'naukri')
        assert after['sync_status'] == 'closed'
    finally:
        _cleanup(job_id)


def test_duplicate_delivery_uses_update_not_second_publish(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    calls = {'publish': 0, 'update': 0}

    class OkResult:
        success = True
        provider = 'linkedin'
        error = None
        external_job_id = 'LI-KEEP'
        external_status = 'active'

        def to_dict(self):
            return {'success': True, 'external_job_id': 'LI-KEEP'}

    class Agg:
        results = [OkResult()]

    def fake_publish(self, snapshot, **kwargs):
        calls['publish'] += 1
        repo.upsert_external_job(
            company, job_id, 'linkedin',
            external_job_id='LI-KEEP', sync_status='published',
            mark_published=True, clear_lease=True,
        )
        return Agg()

    def fake_update(self, snapshot, **kwargs):
        calls['update'] += 1
        repo.upsert_external_job(
            company, job_id, 'linkedin',
            external_job_id='LI-KEEP', sync_status='published',
            mark_published=True, clear_lease=True,
        )
        return Agg()

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.publish_job',
        fake_publish,
    )
    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.update_job',
        fake_update,
    )
    monkeypatch.setattr(
        'app.domains.integrations.service.publish_service.load_job_snapshot',
        lambda *a, **k: MagicMock(job_id=job_id, company_key=company, to_dict=lambda: {}),
    )

    try:
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            external_job_id='LI-KEEP',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
        )
        claimed = repo.claim_pending_external_jobs('worker-I', limit=50, job_id=job_id)
        row = next(r for r in claimed if r['job_id'] == job_id)
        outbox_mod.process_external_job_row(row)
        assert calls['update'] == 1
        assert calls['publish'] == 0
    finally:
        _cleanup(job_id)


def test_startup_drain_discovers_pending(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    processed = {'n': 0}

    monkeypatch.setattr(
        outbox_mod,
        'process_external_job_row',
        lambda row: processed.__setitem__('n', processed['n'] + 1)
        or repo.upsert_external_job(
            row['company_key'],
            row['job_id'],
            row['provider'],
            sync_status='published',
            clear_lease=True,
        ),
    )
    try:
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
        )
        n = outbox_mod.drain_outbox(limit=50, worker_id='startup-worker', job_id=job_id)
        assert n >= 1
        assert processed['n'] >= 1
        after = repo.get_external_job(job_id, 'linkedin')
        assert after['sync_status'] == 'published'
    finally:
        _cleanup(job_id)


def test_concurrent_workers_process_different_tasks(pg):
    company = f'co-{uuid.uuid4().hex[:6]}'
    job_a = _unique_job()
    job_b = _unique_job()
    try:
        for jid in (job_a, job_b):
            repo.upsert_external_job(
                company,
                jid,
                'linkedin',
                sync_status='pending',
                pending_operation='publish',
                due_now=True,
                clear_lease=True,
            )
        a = repo.claim_pending_external_jobs('w-1', limit=1, job_id=job_a)
        b = repo.claim_pending_external_jobs('w-2', limit=1, job_id=job_b)
        ids_a = {r['id'] for r in a}
        ids_b = {r['id'] for r in b}
        assert ids_a.isdisjoint(ids_b)
        assert len(ids_a | ids_b) >= 2 or (len(ids_a) + len(ids_b) >= 2)
    finally:
        _cleanup(job_a)
        _cleanup(job_b)


def test_recover_external_id_from_sync_logs(pg):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    from app.database.connection.db import db_run

    try:
        repo.insert_sync_log(
            company,
            'linkedin',
            'publish',
            'success',
            job_id=job_id,
            external_job_id='LI-RECOVERED',
            response_payload={'external_job_id': 'LI-RECOVERED'},
        )
        got = repo.recover_external_job_id_from_logs(job_id, 'linkedin')
        assert got == 'LI-RECOVERED'
    finally:
        _cleanup(job_id)
