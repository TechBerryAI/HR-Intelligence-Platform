"""Durable PostgreSQL outbox drain for external_jobs publish/close."""
from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from app.domains.integrations import repository as repo
from app.domains.integrations.worker import retry as retry_mod

logger = logging.getLogger(__name__)

_worker_id = f'int-{os.getpid()}-{uuid.uuid4().hex[:8]}'
_drain_thread: threading.Thread | None = None
_drain_stop = threading.Event()
_DRAIN_INTERVAL_SECONDS = 5


def get_outbox_worker_id() -> str:
    return _worker_id


def _ensure_external_id(row: dict) -> dict:
    """Hydrate external_job_id from sync_logs when a prior success was not persisted."""
    if row.get('external_job_id'):
        return row
    recovered = repo.recover_external_job_id_from_logs(row['job_id'], row['provider'])
    if not recovered:
        return row
    repo.upsert_external_job(
        row['company_key'],
        row['job_id'],
        row['provider'],
        external_job_id=recovered,
        sync_status='pending',
        pending_operation=row.get('pending_operation') or 'publish',
        retry_count=int(row.get('retry_count') or 0),
        clear_lease=False,
    )
    row = dict(row)
    row['external_job_id'] = recovered
    logger.info(
        '[integrations] recovered external_job_id=%s for %s/%s from sync_logs',
        recovered,
        row['job_id'],
        row['provider'],
    )
    return row


def process_external_job_row(row: dict) -> None:
    """Process one claimed external_jobs outbox row."""
    from app.domains.integrations.service.manager import IntegrationManagerService
    from app.domains.integrations.service.publish_service import load_job_snapshot

    manager = IntegrationManagerService()
    company_key = row['company_key']
    job_id = row['job_id']
    provider = row['provider']
    retry_count = int(row.get('retry_count') or 0)
    operation = (row.get('pending_operation') or 'publish').strip().lower()
    row = _ensure_external_id(row)

    logger.info(
        '[integrations] outbox processing id=%s op=%s job=%s provider=%s retry=%s',
        row.get('id'),
        operation,
        job_id,
        provider,
        retry_count,
    )

    if operation == 'close':
        if not row.get('external_job_id'):
            repo.upsert_external_job(
                company_key,
                job_id,
                provider,
                sync_status='closed',
                error_message=None,
                retry_count=retry_count,
                clear_lease=True,
            )
            return
        aggregate = manager.close_job(
            company_key, job_id, providers=[provider], retry_count=retry_count
        )
    else:
        snapshot = load_job_snapshot(job_id, company_key)
        if not snapshot:
            logger.warning('[integrations] outbox job not found: %s', job_id)
            repo.upsert_external_job(
                company_key,
                job_id,
                provider,
                sync_status='failed',
                error_message='Job not found',
                retry_count=retry_count,
                clear_lease=True,
            )
            return
        # Prefer update when we already have an external id (idempotent redelivery).
        if operation == 'update' or row.get('external_job_id'):
            aggregate = manager.update_job(
                snapshot, providers=[provider], retry_count=retry_count
            )
        else:
            aggregate = manager.publish_job(
                snapshot,
                providers=[provider],
                auto_publish_only=False,
                retry_count=retry_count,
            )

    _handle_outbox_result(aggregate, company_key, job_id, provider, retry_count, operation)


def _handle_outbox_result(
    aggregate,
    company_key: str,
    job_id: str,
    provider: str,
    retry_count: int,
    operation: str,
) -> None:
    for result in aggregate.results:
        if result.provider != provider:
            continue
        if result.success:
            # manager already persisted published/closed and cleared lease via upsert
            return
        next_retry = retry_count + 1
        if retry_mod.should_retry(next_retry - 1):
            delay = retry_mod.backoff_seconds(retry_count)
            next_at = datetime.now(timezone.utc) + timedelta(seconds=min(delay, 300.0))
            repo.schedule_external_job_retry(
                company_key,
                job_id,
                provider,
                pending_operation=operation if operation != 'republish' else 'publish',
                retry_count=next_retry,
                error_message=result.error,
                next_attempt_at=next_at,
            )
            logger.info(
                '[integrations] outbox retry scheduled for %s/%s at %s (attempt %s)',
                job_id,
                provider,
                next_at.isoformat(),
                next_retry,
            )
        else:
            retry_mod.mark_dead(company_key, job_id, provider, result.error, next_retry)


def drain_outbox(*, limit: int = 10, worker_id: str | None = None, job_id: str | None = None) -> int:
    """Claim and process up to ``limit`` pending rows. Returns number processed."""
    wid = worker_id or _worker_id
    claimed = repo.claim_pending_external_jobs(wid, limit=limit, job_id=job_id)
    for row in claimed:
        try:
            process_external_job_row(row)
        except Exception:
            logger.exception(
                '[integrations] outbox row failed id=%s job=%s',
                row.get('id'),
                row.get('job_id'),
            )
            try:
                repo.release_external_job_lease(int(row['id']))
            except Exception:
                pass
    return len(claimed)


def _drain_loop() -> None:
    logger.info('[integrations] outbox drain loop started (worker=%s)', _worker_id)
    # Startup recovery: pick up sticky pending immediately
    try:
        drain_outbox(limit=25)
    except Exception:
        logger.exception('[integrations] startup outbox drain failed')
    while not _drain_stop.is_set():
        try:
            drain_outbox(limit=10)
        except Exception:
            logger.exception('[integrations] outbox drain tick failed')
        _drain_stop.wait(_DRAIN_INTERVAL_SECONDS)


def start_outbox_drain() -> None:
    global _drain_thread
    if _drain_thread and _drain_thread.is_alive():
        return
    _drain_stop.clear()
    _drain_thread = threading.Thread(
        target=_drain_loop, name='integration-outbox-drain', daemon=True
    )
    _drain_thread.start()


def stop_outbox_drain(*, timeout: float = 5.0) -> None:
    """Stop drain loop and release this worker's leases so tasks become reclaimable."""
    global _drain_thread
    _drain_stop.set()
    t = _drain_thread
    if t and t.is_alive() and t is not threading.current_thread():
        t.join(timeout=timeout)
    if t and not t.is_alive():
        _drain_thread = None
    try:
        n = repo.release_leases_for_worker(_worker_id)
        if n:
            logger.info('[integrations] released %s outbox lease(s) on shutdown', n)
    except Exception:
        logger.exception('[integrations] lease release on shutdown failed')
