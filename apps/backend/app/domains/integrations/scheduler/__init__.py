"""Periodic auto-sync for HTTP custom providers with auto_sync enabled."""
from __future__ import annotations

import logging
import threading
import time

from app.domains.integrations.config import get_auto_sync_interval_seconds, is_builtin
from app.domains.integrations import repository as repo
from app.domains.integrations.service.manager import IntegrationManagerService

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_stop = threading.Event()


def tick_auto_sync() -> None:
    """Enqueue/run sync for enabled auto_sync HTTP providers."""
    manager = IntegrationManagerService()
    try:
        rows = repo.list_auto_sync_http_providers()
    except Exception as exc:
        logger.warning('[integrations] auto-sync list failed: %s', exc)
        return

    for row in rows:
        provider = (row.get('provider') or '').strip().lower()
        company_key = row.get('company_key') or ''
        if not provider or not company_key:
            continue
        if is_builtin(provider):
            # Built-ins keep their own sync implementations; still allow auto_sync
            pass
        settings = repo.row_to_settings(row)
        adapter = (settings.get('adapter') or '').lower()
        if not is_builtin(provider) and adapter != 'http':
            continue
        try:
            result = manager.sync_provider(company_key, provider)
            logger.info(
                '[integrations] auto-sync %s/%s success=%s imported=%s',
                company_key,
                provider,
                result.success,
                result.imported_count,
            )
        except Exception:
            logger.exception('[integrations] auto-sync failed for %s/%s', company_key, provider)


def _loop():
    interval = get_auto_sync_interval_seconds()
    logger.info('[integrations] auto-sync scheduler started (interval=%ss)', interval)
    # Initial delay so app finishes boot
    if _stop.wait(15):
        return
    while not _stop.is_set():
        try:
            tick_auto_sync()
        except Exception:
            logger.exception('[integrations] auto-sync tick error')
        if _stop.wait(get_auto_sync_interval_seconds()):
            break


def start_auto_sync_scheduler() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name='integration-auto-sync', daemon=True)
    _thread.start()


def stop_auto_sync_scheduler() -> None:
    _stop.set()
