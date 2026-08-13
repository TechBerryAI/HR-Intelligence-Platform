"""Bootstrap integrations domain (providers, events, workers)."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def init_integrations(*, start_auto_sync: bool | None = None) -> None:
    """
    Initialize integration providers, event subscribers, and per-process workers.

    Auto-sync is a **singleton** across the fleet. It must NOT start in every
    Gunicorn web worker. Pass ``start_auto_sync=True`` or set
    ``RUN_INTEGRATION_AUTO_SYNC=1`` only in a dedicated scheduler process.
    """
    from app.domains.integrations.provider.factory import ensure_default_providers
    from app.domains.integrations.provider.calendar_factory import ensure_default_calendar_providers
    from app.domains.integrations.events.subscribers import register_subscribers
    from app.domains.integrations.worker.handlers import start_workers

    ensure_default_providers()
    ensure_default_calendar_providers()
    register_subscribers()
    start_workers()

    if start_auto_sync is None:
        start_auto_sync = _env_flag('RUN_INTEGRATION_AUTO_SYNC', False)
    if start_auto_sync:
        from app.domains.integrations.scheduler import start_auto_sync_scheduler

        start_auto_sync_scheduler()
        logger.info('[integrations] auto-sync scheduler enabled in this process')
    else:
        logger.info(
            '[integrations] auto-sync scheduler not started '
            '(set RUN_INTEGRATION_AUTO_SYNC=1 in a dedicated process)'
        )
    logger.info('[integrations] framework initialized')
