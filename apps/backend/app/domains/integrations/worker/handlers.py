"""Process queued integration tasks (in-memory fast path + durable outbox)."""
from __future__ import annotations

import atexit
import logging

from app.domains.integrations.worker.outbox import drain_outbox, start_outbox_drain, stop_outbox_drain
from app.domains.integrations.worker.queue import get_queue

logger = logging.getLogger(__name__)


def process_task(task: dict) -> None:
    """
    In-memory queue handler.

    Durable work lives in external_jobs. The memory queue only hints the local
    process to drain claimable rows immediately.
    """
    task_type = (task.get('type') or '').strip().lower()
    if task_type in (
        'outbox_drain',
        'publish',
        'republish',
        'update',
        'close',
        'sync',
    ):
        # Always drain via CAS claim so duplicate in-memory hints cannot double-run.
        if task_type == 'sync':
            # Sync remains request/scheduler driven; still safe to no-op here for hints.
            from app.domains.integrations.service.manager import IntegrationManagerService

            provider = (task.get('provider') or '') or ''
            providers = task.get('providers') or []
            provider = provider or (providers[0] if providers else '')
            company_key = task.get('company_key') or ''
            if provider and company_key:
                IntegrationManagerService().sync_provider(company_key, provider)
            return
        n = drain_outbox(limit=20)
        logger.info('[integrations] memory hint drained %s outbox row(s)', n)
        return

    logger.warning('[integrations] unknown task type: %s', task_type)


def start_workers() -> None:
    queue = get_queue()
    queue.start(process_task)
    start_outbox_drain()
    atexit.register(stop_outbox_drain)


def stop_workers() -> None:
    stop_outbox_drain()
    try:
        get_queue().stop()
    except Exception:
        logger.exception('[integrations] queue stop failed')
