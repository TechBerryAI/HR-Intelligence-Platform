"""Final production acceptance: durable outbox cannot lose work / duplicate claims.

All scenarios run against live PostgreSQL. Providers are mocked unless noted.
Process crash is simulated by skipping memory hint / expiring leases / raising
before final local success commit.
"""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.domains.integrations import repository as repo
from app.domains.integrations.service import publish_service
from app.domains.integrations.service.manager import IntegrationManagerService
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
    return f'ACC{uuid.uuid4().hex[:8].upper()}'


def _cleanup(job_id: str):
    from app.database.connection.db import db_run

    db_run('DELETE FROM sync_logs WHERE job_id = ?', (job_id,))
    db_run('DELETE FROM external_jobs WHERE job_id = ?', (job_id,))


def test_acc1_publish_durable_survives_memory_skip_and_drain(pg, monkeypatch):
    """Request publish → durable row → no memory enqueue → restart drain → executes."""
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    monkeypatch.setattr(publish_service, '_best_effort_memory_hint', lambda t: None)
    monkeypatch.setattr(
        repo,
        'list_enabled_providers',
        lambda ck: [{'provider': 'linkedin'}],
    )
    executed = {'n': 0}

    def fake_process(row):
        executed['n'] += 1
        repo.upsert_external_job(
            row['company_key'],
            row['job_id'],
            row['provider'],
            external_job_id='LI-DURABLE-1',
            sync_status='published',
            mark_published=True,
            clear_lease=True,
        )

    monkeypatch.setattr(outbox_mod, 'process_external_job_row', fake_process)
    try:
        result = publish_service.enqueue_publish(company, job_id, providers=['linkedin'])
        assert result['durable'] is True
        row = repo.get_external_job(job_id, 'linkedin')
        assert row['sync_status'] == 'pending'
        n = outbox_mod.drain_outbox(limit=20, worker_id='acc1-restart', job_id=job_id)
        assert n == 1
        assert executed['n'] == 1
        after = repo.get_external_job(job_id, 'linkedin')
        assert after['sync_status'] == 'published'
        assert after['external_job_id'] == 'LI-DURABLE-1'
    finally:
        _cleanup(job_id)


def test_acc2_close_durable_survives_crash_before_drain(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    monkeypatch.setattr(publish_service, '_best_effort_memory_hint', lambda t: None)
    executed = {'n': 0}

    def fake_process(row):
        executed['n'] += 1
        assert (row.get('pending_operation') or '') == 'close'
        repo.upsert_external_job(
            row['company_key'],
            row['job_id'],
            row['provider'],
            external_job_id='NK-CLOSE-1',
            sync_status='closed',
            clear_lease=True,
        )

    monkeypatch.setattr(outbox_mod, 'process_external_job_row', fake_process)
    try:
        repo.upsert_external_job(
            company,
            job_id,
            'naukri',
            external_job_id='NK-CLOSE-1',
            sync_status='published',
            mark_published=True,
        )
        result = publish_service.enqueue_close(company, job_id, providers=['naukri'])
        assert result['durable'] is True
        pending = repo.get_external_job(job_id, 'naukri')
        assert pending['sync_status'] == 'pending'
        assert pending['pending_operation'] == 'close'
        n = outbox_mod.drain_outbox(limit=20, worker_id='acc2-restart', job_id=job_id)
        assert n == 1
        assert executed['n'] == 1
        assert repo.get_external_job(job_id, 'naukri')['sync_status'] == 'closed'
    finally:
        _cleanup(job_id)


def test_acc3_parallel_claim_only_one_wins(pg):
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
        barrier = threading.Barrier(2)
        results: list[list] = [[], []]

        def claim(slot: int, wid: str):
            barrier.wait(timeout=5)
            results[slot] = repo.claim_pending_external_jobs(wid, limit=10, job_id=job_id)

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(claim, 0, 'acc3-A')
            f2 = pool.submit(claim, 1, 'acc3-B')
            f1.result(timeout=10)
            f2.result(timeout=10)

        a_ids = {r['id'] for r in results[0] if r['job_id'] == job_id}
        b_ids = {r['id'] for r in results[1] if r['job_id'] == job_id}
        assert len(a_ids | b_ids) == 1
        assert a_ids.isdisjoint(b_ids)
        assert (len(a_ids) == 1 and len(b_ids) == 0) or (len(a_ids) == 0 and len(b_ids) == 1)
    finally:
        _cleanup(job_id)


def test_acc4_lease_expire_then_other_worker_completes(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    from app.database.connection.db import db_run

    class OkResult:
        success = True
        provider = 'linkedin'
        error = None
        external_job_id = 'LI-LEASE'
        external_status = 'active'

        def to_dict(self):
            return {'success': True, 'external_job_id': 'LI-LEASE'}

    class Agg:
        results = [OkResult()]

    def fake_publish(self, snapshot, **kwargs):
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            external_job_id='LI-LEASE',
            sync_status='published',
            mark_published=True,
            clear_lease=True,
        )
        return Agg()

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.publish_job',
        fake_publish,
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
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
        )
        a = repo.claim_pending_external_jobs('acc4-A', limit=20, job_id=job_id)
        row = next(r for r in a if r['job_id'] == job_id)
        past = datetime.now(timezone.utc) - timedelta(seconds=90)
        db_run('UPDATE external_jobs SET leased_until = ? WHERE id = ?', (past, row['id']))
        b = repo.claim_pending_external_jobs('acc4-B', limit=20, job_id=job_id)
        claimed = next(r for r in b if r['id'] == row['id'])
        assert claimed.get('leased_by') == 'acc4-B'
        outbox_mod.process_external_job_row(claimed)
        after = repo.get_external_job(job_id, 'linkedin')
        assert after['sync_status'] == 'published'
        assert after['external_job_id'] == 'LI-LEASE'
    finally:
        _cleanup(job_id)


def test_acc5_provider_success_crash_before_final_uses_update(pg, monkeypatch):
    """Provider returns remote id; local dies before published; retry must update."""
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    calls = {'publish': 0, 'update': 0}

    class FakeProvider:
        provider_type = 'linkedin'

        def publish(self, job, config):
            calls['publish'] += 1
            from app.domains.integrations.dto import PublishResult

            return PublishResult(
                success=True,
                provider='linkedin',
                external_job_id='LI-CRASH-1',
                external_status='published',
                message='ok',
            )

        def update(self, job, external_job_id, config):
            calls['update'] += 1
            from app.domains.integrations.dto import PublishResult

            return PublishResult(
                success=True,
                provider='linkedin',
                external_job_id=external_job_id,
                external_status='updated',
                message='ok',
            )

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.get_provider',
        lambda name: FakeProvider(),
    )
    monkeypatch.setattr(
        'app.domains.integrations.service.manager._log_call',
        lambda *a, **k: None,
    )

    snapshot = MagicMock()
    snapshot.job_id = job_id
    snapshot.company_key = company
    snapshot.to_dict = lambda: {'jobId': job_id}

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
        mgr = IntegrationManagerService()
        original_persist = mgr._persist_external

        def crash_after_bind(*args, **kwargs):
            raise RuntimeError('simulated crash after provider success')

        mgr._persist_external = crash_after_bind  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match='simulated crash'):
            mgr._publish_one(snapshot, MagicMock(provider='linkedin'), retry_count=0)

        mid = repo.get_external_job(job_id, 'linkedin')
        assert mid.get('external_job_id') == 'LI-CRASH-1', (
            f'external_job_id not durable after provider success (got {mid.get("external_job_id")!r}); '
            'retry would re-publish and can duplicate'
        )
        assert mid['sync_status'] == 'pending'

        mgr._persist_external = original_persist  # type: ignore[method-assign]
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            external_job_id='LI-CRASH-1',
            sync_status='pending',
            pending_operation='update',
            due_now=True,
            clear_lease=True,
        )
        result = mgr._publish_one(snapshot, MagicMock(provider='linkedin'), retry_count=1)
        assert result.success
        assert calls['publish'] == 1
        assert calls['update'] == 1
        after = repo.get_external_job(job_id, 'linkedin')
        assert after['sync_status'] == 'published'
        assert after['external_job_id'] == 'LI-CRASH-1'
    finally:
        _cleanup(job_id)


def test_acc6_existing_external_id_never_recreates(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    calls = {'publish': 0, 'update': 0}

    class FakeProvider:
        def publish(self, job, config):
            calls['publish'] += 1
            from app.domains.integrations.dto import PublishResult

            return PublishResult(success=True, provider='linkedin', external_job_id='NEW')

        def update(self, job, external_job_id, config):
            calls['update'] += 1
            from app.domains.integrations.dto import PublishResult

            return PublishResult(
                success=True,
                provider='linkedin',
                external_job_id=external_job_id,
                external_status='updated',
            )

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.get_provider',
        lambda name: FakeProvider(),
    )
    monkeypatch.setattr(
        'app.domains.integrations.service.manager._log_call',
        lambda *a, **k: None,
    )
    snapshot = MagicMock(job_id=job_id, company_key=company, to_dict=lambda: {})
    try:
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            external_job_id='LI-EXISTING',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
        )
        mgr = IntegrationManagerService()
        mgr._publish_one(snapshot, MagicMock(provider='linkedin'), retry_count=0)
        assert calls['publish'] == 0
        assert calls['update'] == 1
    finally:
        _cleanup(job_id)


def test_acc7_retry_then_success(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'
    attempts = {'n': 0}

    class FailThenOk:
        success = False
        provider = 'linkedin'
        error = 'transient'
        external_job_id = None
        external_status = None

        def to_dict(self):
            return {'success': self.success}

    class Agg:
        def __init__(self, ok: bool):
            r = FailThenOk()
            r.success = ok
            r.error = None if ok else 'transient'
            r.external_job_id = 'LI-R' if ok else None
            self.results = [r]

    def fake_publish(self, snapshot, **kwargs):
        attempts['n'] += 1
        if attempts['n'] == 1:
            return Agg(False)
        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            external_job_id='LI-R',
            sync_status='published',
            mark_published=True,
            clear_lease=True,
        )
        return Agg(True)

    monkeypatch.setattr(
        'app.domains.integrations.service.manager.IntegrationManagerService.publish_job',
        fake_publish,
    )
    monkeypatch.setattr(
        'app.domains.integrations.service.publish_service.load_job_snapshot',
        lambda *a, **k: MagicMock(job_id=job_id, company_key=company, to_dict=lambda: {}),
    )
    monkeypatch.setattr(
        'app.domains.integrations.config.get_max_retries',
        lambda: 5,
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
        claimed = repo.claim_pending_external_jobs('acc7-1', limit=20, job_id=job_id)
        row = next(r for r in claimed if r['job_id'] == job_id)
        outbox_mod.process_external_job_row(row)
        mid = repo.get_external_job(job_id, 'linkedin')
        assert mid['sync_status'] == 'pending'
        assert int(mid['retry_count']) == 1
        assert mid.get('next_attempt_at') is not None

        repo.upsert_external_job(
            company,
            job_id,
            'linkedin',
            sync_status='pending',
            pending_operation='publish',
            due_now=True,
            clear_lease=True,
            retry_count=int(mid['retry_count']),
        )
        claimed2 = repo.claim_pending_external_jobs('acc7-2', limit=20, job_id=job_id)
        row2 = next(r for r in claimed2 if r['job_id'] == job_id)
        outbox_mod.process_external_job_row(row2)
        after = repo.get_external_job(job_id, 'linkedin')
        assert after['sync_status'] == 'published'
        assert attempts['n'] == 2
    finally:
        _cleanup(job_id)


def test_acc7b_max_retry_dead_letter(pg, monkeypatch):
    job_id = _unique_job()
    company = f'co-{uuid.uuid4().hex[:6]}'

    class FailResult:
        success = False
        provider = 'linkedin'
        error = 'permanent'
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
            retry_count=1,
        )
        claimed = repo.claim_pending_external_jobs('acc7b', limit=20, job_id=job_id)
        row = next(r for r in claimed if r['job_id'] == job_id)
        outbox_mod.process_external_job_row(row)
        assert repo.get_external_job(job_id, 'linkedin')['sync_status'] == 'dead'
    finally:
        _cleanup(job_id)


def test_acc8_startup_eligibility_respects_active_leases(pg):
    from app.database.connection.db import db_run

    company = f'co-{uuid.uuid4().hex[:6]}'
    job_none = _unique_job()
    job_expired = _unique_job()
    job_active = _unique_job()
    try:
        for jid in (job_none, job_expired, job_active):
            repo.upsert_external_job(
                company,
                jid,
                'linkedin',
                sync_status='pending',
                pending_operation='publish',
                due_now=True,
                clear_lease=True,
            )
        c_exp = repo.claim_pending_external_jobs('acc8-exp', limit=5, job_id=job_expired)
        row_exp = next(r for r in c_exp if r['job_id'] == job_expired)
        past = datetime.now(timezone.utc) - timedelta(seconds=30)
        db_run('UPDATE external_jobs SET leased_until = ? WHERE id = ?', (past, row_exp['id']))
        c_act = repo.claim_pending_external_jobs('acc8-hold', limit=5, job_id=job_active)
        row_act = next(r for r in c_act if r['job_id'] == job_active)
        future = datetime.now(timezone.utc) + timedelta(minutes=10)
        db_run(
            'UPDATE external_jobs SET leased_by = ?, leased_until = ? WHERE id = ?',
            ('acc8-hold', future, row_act['id']),
        )

        claimed = repo.claim_pending_external_jobs('acc8-startup', limit=50)
        ids = {r['job_id'] for r in claimed}
        assert job_none in ids
        assert job_expired in ids
        assert job_active not in ids
    finally:
        _cleanup(job_none)
        _cleanup(job_expired)
        _cleanup(job_active)


def test_acc9_two_drain_workers_no_duplicate_process(pg, monkeypatch):
    company = f'co-{uuid.uuid4().hex[:6]}'
    job_a = _unique_job()
    job_b = _unique_job()
    processed: list[str] = []
    lock = threading.Lock()

    def fake_process(row):
        with lock:
            processed.append(f"{row['job_id']}:{row['provider']}")
        repo.upsert_external_job(
            row['company_key'],
            row['job_id'],
            row['provider'],
            sync_status='published',
            clear_lease=True,
        )

    monkeypatch.setattr(outbox_mod, 'process_external_job_row', fake_process)
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
        barrier = threading.Barrier(2)

        def drain(wid: str):
            barrier.wait(timeout=5)
            return outbox_mod.drain_outbox(limit=10, worker_id=wid)

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(drain, 'acc9-w1')
            f2 = pool.submit(drain, 'acc9-w2')
            n1 = f1.result(timeout=15)
            n2 = f2.result(timeout=15)

        assert n1 + n2 == 2
        assert len(processed) == 2
        assert len(set(processed)) == 2
    finally:
        _cleanup(job_a)
        _cleanup(job_b)


def test_acc11_outbox_columns_and_index_present(pg):
    from app.database.connection.db import db_get, db_all

    cols = {
        r['column_name']
        for r in db_all(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'external_jobs'
              AND column_name IN ('leased_by','leased_until','next_attempt_at','pending_operation')
            """
        )
    }
    assert cols == {'leased_by', 'leased_until', 'next_attempt_at', 'pending_operation'}
    idx = db_get(
        """
        SELECT 1 AS ok FROM pg_indexes
        WHERE tablename = 'external_jobs' AND indexname = 'ix_external_jobs_outbox_claim'
        """
    )
    assert idx
    nulls = {
        r['column_name']: r['is_nullable']
        for r in db_all(
            """
            SELECT column_name, is_nullable FROM information_schema.columns
            WHERE table_name = 'external_jobs'
              AND column_name IN ('leased_by','leased_until','pending_operation','next_attempt_at')
            """
        )
    }
    assert nulls['leased_by'] == 'YES'
    assert nulls['leased_until'] == 'YES'
    assert nulls['pending_operation'] == 'YES'
