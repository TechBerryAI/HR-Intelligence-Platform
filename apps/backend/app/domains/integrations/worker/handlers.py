"""Process queued integration tasks."""
from __future__ import annotations

import logging

from app.domains.integrations.service.manager import IntegrationManagerService
from app.domains.integrations.service.publish_service import load_job_snapshot
from app.domains.integrations.worker import retry as retry_mod
from app.domains.integrations.worker.queue import get_queue
from app.domains.integrations import repository as repo

logger = logging.getLogger(__name__)

_manager = IntegrationManagerService()


def process_task(task: dict) -> None:
    task_type = (task.get('type') or '').strip().lower()
    company_key = task.get('company_key') or ''
    job_id = task.get('job_id') or ''
    providers = task.get('providers')
    retry_count = int(task.get('retry_count') or 0)
    auto_publish_only = bool(task.get('auto_publish_only'))

    logger.info(
        '[integrations] processing %s job=%s company=%s retry=%s',
        task_type,
        job_id,
        company_key,
        retry_count,
    )

    if task_type in ('publish', 'republish', 'update'):
        snapshot = load_job_snapshot(job_id, company_key)
        if not snapshot:
            logger.warning('[integrations] job not found: %s', job_id)
            return
        if task_type == 'update':
            aggregate = _manager.update_job(snapshot, providers=providers, retry_count=retry_count)
        else:
            aggregate = _manager.publish_job(
                snapshot,
                providers=providers,
                auto_publish_only=auto_publish_only and task_type == 'publish',
                retry_count=retry_count,
            )
        _handle_failures(aggregate, company_key, job_id, retry_count, task_type)
        return

    if task_type == 'close':
        aggregate = _manager.close_job(company_key, job_id, providers=providers, retry_count=retry_count)
        _handle_failures(aggregate, company_key, job_id, retry_count, 'close')
        return

    if task_type == 'sync':
        provider = (task.get('provider') or (providers[0] if providers else '')) or ''
        if provider:
            _manager.sync_provider(company_key, provider)
        return

    logger.warning('[integrations] unknown task type: %s', task_type)


def _handle_failures(aggregate, company_key: str, job_id: str, retry_count: int, operation: str) -> None:
    queue = get_queue()
    for result in aggregate.results:
        if result.success:
            continue
        next_retry = retry_count + 1
        if retry_mod.should_retry(next_retry - 1):
            logger.info(
                '[integrations] scheduling retry %s for %s/%s',
                next_retry,
                job_id,
                result.provider,
            )
            retry_mod.sleep_backoff(retry_count)
            repo.upsert_external_job(
                company_key,
                job_id,
                result.provider,
                sync_status='pending',
                error_message=result.error,
                retry_count=next_retry,
            )
            queue.enqueue({
                'type': operation if operation != 'republish' else 'publish',
                'company_key': company_key,
                'job_id': job_id,
                'providers': [result.provider],
                'auto_publish_only': False,
                'retry_count': next_retry,
            })
        else:
            retry_mod.mark_dead(company_key, job_id, result.provider, result.error, next_retry)


def start_workers() -> None:
    queue = get_queue()
    queue.start(process_task)
