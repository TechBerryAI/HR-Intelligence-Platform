"""Enqueue publish / republish / retry tasks (Postgres outbox is source of truth)."""
from __future__ import annotations

import logging

from app.database.connection.db import db_get
from app.domains.integrations import repository as repo
from app.domains.integrations.mapper.internal_job import job_row_to_snapshot
from app.domains.integrations.worker.queue import get_queue

logger = logging.getLogger(__name__)


def _best_effort_memory_hint(task: dict) -> None:
    """Fast-path hint only — durability does not depend on this."""
    try:
        get_queue().enqueue(task)
    except Exception as exc:
        logger.warning(
            '[integrations] in-memory enqueue skipped (outbox still durable): %s',
            exc,
        )


def enqueue_publish(
    company_key: str,
    job_id: str,
    *,
    providers: list[str] | None = None,
    auto_publish_only: bool = False,
    operation: str = 'publish',
) -> dict:
    op = (operation or 'publish').strip().lower() or 'publish'
    target_providers = providers
    if not target_providers:
        rows = (
            repo.list_enabled_auto_publish(company_key)
            if auto_publish_only
            else repo.list_enabled_providers(company_key)
        )
        target_providers = [r['provider'] for r in rows]

    for p in target_providers or []:
        # Prefer update when an external id already exists (idempotent redelivery).
        existing = repo.get_external_job(job_id, p)
        row_op = op
        if row_op == 'publish' and existing and existing.get('external_job_id'):
            row_op = 'update'
        repo.upsert_external_job(
            company_key,
            job_id,
            p,
            sync_status='pending',
            error_message=None,
            retry_count=0,
            pending_operation=row_op,
            due_now=True,
            clear_lease=True,
        )

    task = {
        'type': 'outbox_drain',
        'company_key': company_key,
        'job_id': job_id,
        'providers': target_providers,
        'auto_publish_only': auto_publish_only,
        'retry_count': 0,
    }
    _best_effort_memory_hint(task)
    return {
        'queued': True,
        'jobId': job_id,
        'providers': target_providers or [],
        'operation': op,
        'durable': True,
    }


def enqueue_close(company_key: str, job_id: str, providers: list[str] | None = None) -> dict:
    externals = repo.list_external_jobs(company_key, job_id=job_id)
    if providers:
        wanted = {p.strip().lower() for p in providers}
        externals = [e for e in externals if (e.get('provider') or '').lower() in wanted]

    target: list[str] = []
    for row in externals:
        provider = row.get('provider')
        if not provider:
            continue
        # Close only meaningful when we have (or had) an external listing.
        if not row.get('external_job_id') and row.get('sync_status') == 'closed':
            continue
        target.append(provider)
        repo.upsert_external_job(
            company_key,
            job_id,
            provider,
            sync_status='pending',
            error_message=None,
            pending_operation='close',
            due_now=True,
            clear_lease=True,
            retry_count=int(row.get('retry_count') or 0),
        )

    if not target and providers:
        # Ensure durable intent even if no prior row (will no-op at process time).
        for p in providers:
            repo.upsert_external_job(
                company_key,
                job_id,
                p,
                sync_status='pending',
                pending_operation='close',
                due_now=True,
                clear_lease=True,
            )
            target.append(p)

    _best_effort_memory_hint({
        'type': 'outbox_drain',
        'company_key': company_key,
        'job_id': job_id,
        'providers': target,
        'retry_count': 0,
    })
    return {'queued': True, 'jobId': job_id, 'operation': 'close', 'providers': target, 'durable': True}


def enqueue_update(company_key: str, job_id: str, providers: list[str] | None = None) -> dict:
    return enqueue_publish(
        company_key,
        job_id,
        providers=providers,
        auto_publish_only=False,
        operation='update',
    )


def enqueue_retry(company_key: str, external_job_row_id: int) -> dict | None:
    row = repo.get_external_job_by_id(external_job_row_id, company_key)
    if not row:
        return None
    retry_count = int(row.get('retry_count') or 0)
    op = (row.get('pending_operation') or 'publish').strip().lower() or 'publish'
    if row.get('external_job_id') and op == 'publish':
        op = 'update'
    repo.upsert_external_job(
        company_key,
        row['job_id'],
        row['provider'],
        sync_status='pending',
        error_message=None,
        retry_count=retry_count,
        pending_operation=op,
        due_now=True,
        clear_lease=True,
    )
    _best_effort_memory_hint({
        'type': 'outbox_drain',
        'company_key': company_key,
        'job_id': row['job_id'],
        'providers': [row['provider']],
        'auto_publish_only': False,
        'retry_count': retry_count,
    })
    return {
        'queued': True,
        'jobId': row['job_id'],
        'provider': row['provider'],
        'externalJobId': row.get('id'),
        'durable': True,
    }


def load_job_snapshot(job_id: str, company_key: str):
    job = db_get('SELECT * FROM jobs WHERE jdid = ?', (job_id,))
    if not job:
        return None
    return job_row_to_snapshot(job, company_key=company_key)
