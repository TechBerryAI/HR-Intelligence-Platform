"""Future auto-sync scheduler scaffold (no-op tick for now)."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def tick_auto_sync() -> None:
    """Placeholder for periodic provider sync. Wire to APScheduler/celery beat later."""
    logger.debug('[integrations] auto-sync tick (noop)')
