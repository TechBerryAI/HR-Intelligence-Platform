"""Bootstrap integrations domain (providers, events, workers)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def init_integrations() -> None:
    from app.domains.integrations.provider.factory import ensure_default_providers
    from app.domains.integrations.events.subscribers import register_subscribers
    from app.domains.integrations.worker.handlers import start_workers
    from app.domains.integrations.scheduler import start_auto_sync_scheduler

    ensure_default_providers()
    register_subscribers()
    start_workers()
    start_auto_sync_scheduler()
    logger.info('[integrations] framework initialized')
