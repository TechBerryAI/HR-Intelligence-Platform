"""Enqueue publish / republish / retry tasks."""
from __future__ import annotations

import logging

from app.database.connection.db import db_get
from app.domains.integrations import repository as repo
from app.domains.integrations.mapper.internal_job import job_row_to_snapshot
from app.domains.integrations.worker.queue import get_queue

logger = logging.getLogger(__name__)


def enqueue_publish(
    company_key: str,
    job_id: str,
    *,
    providers: list[str] | None = None,
    auto_publish_only: bool = False,
    operation: str = 'publish',
) -> dict:
    queue = get_queue()
    task = {
        'type': operation,
        'company_key': company_key,
        'job_id': job_id,
        'providers': providers,
        'auto_publish_only': auto_publish_only,
        'retry_count': 0,
    }
    # Mark pending rows for visibility
    target_providers = providers
    if not target_providers:
        rows = (
            repo.list_enabled_auto_publish(company_key)
            if auto_publish_only
            else repo.list_enabled_providers(company_key)
        )
        target_providers = [r['provider'] for r in rows]
    for p in target_providers or []:
        repo.upsert_external_job(
            company_key,
            job_id,
            p,
            sync_status='pending',
            error_message=None,
        )
    queue.enqueue(task)
    return {'queued': True, 'jobId': job_id, 'providers': target_providers or [], 'operation': operation}


def enqueue_close(company_key: str, job_id: str, providers: list[str] | None = None) -> dict:
    queue = get_queue()
    queue.enqueue({
        'type': 'close',
        'company_key': company_key,
        'job_id': job_id,
        'providers': providers,
        'retry_count': 0,
    })
    return {'queued': True, 'jobId': job_id, 'operation': 'close'}


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
    repo.upsert_external_job(
        company_key,
        row['job_id'],
        row['provider'],
        sync_status='pending',
        error_message=None,
        retry_count=retry_count,
    )
    queue = get_queue()
    queue.enqueue({
        'type': 'publish',
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
    }


def load_job_snapshot(job_id: str, company_key: str):
    job = db_get('SELECT * FROM jobs WHERE jdid = ?', (job_id,))
    if not job:
        return None
    return job_row_to_snapshot(job, company_key=company_key)
