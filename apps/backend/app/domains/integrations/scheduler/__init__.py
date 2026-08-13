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

# Stable Postgres advisory-lock key for cross-process singleton ticks.
AUTO_SYNC_ADVISORY_LOCK_KEY = 872_014_001


def try_acquire_auto_sync_lock(conn) -> bool:
    """Session-level advisory lock. Must unlock on the same connection."""
    with conn.cursor() as cur:
        cur.execute('SELECT pg_try_advisory_lock(%s)', (AUTO_SYNC_ADVISORY_LOCK_KEY,))
        row = cur.fetchone()
    return bool(row and row[0])


def release_auto_sync_lock(conn) -> None:
    with conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_unlock(%s)', (AUTO_SYNC_ADVISORY_LOCK_KEY,))
        cur.fetchone()


def tick_auto_sync(*, _force: bool = False) -> bool:
    """
    Run one auto-sync tick if this process holds the distributed lock.

    Returns True if this process performed the tick, False if skipped (another
    scheduler owns the lock or lock acquisition failed).
    """
    from app.database.connection.db import _create_connection

    if _force:
        _tick_auto_sync_unlocked()
        return True

    conn = None
    acquired = False
    try:
        conn = _create_connection()
        acquired = try_acquire_auto_sync_lock(conn)
        conn.commit()
        if not acquired:
            logger.info('[integrations] auto-sync tick skipped (another scheduler holds lock)')
            return False
        _tick_auto_sync_unlocked()
        return True
    except Exception:
        logger.exception('[integrations] auto-sync tick error')
        return False
    finally:
        if conn is not None:
            try:
                if acquired:
                    release_auto_sync_lock(conn)
                    conn.commit()
            except Exception:
                logger.exception('[integrations] auto-sync lock release failed')
            try:
                conn.close()
            except Exception:
                pass


def _tick_auto_sync_unlocked() -> None:
    """Drain durable outbox + sync auto_sync HTTP providers (caller holds lock)."""
    try:
        from app.domains.integrations.worker.outbox import drain_outbox

        n = drain_outbox(limit=25)
        if n:
            logger.info('[integrations] scheduler drained %s outbox row(s)', n)
    except Exception:
        logger.exception('[integrations] scheduler outbox drain failed')

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


def stop_auto_sync_scheduler(timeout: float = 5.0) -> None:
    """Signal the auto-sync loop to stop and join the thread when possible."""
    global _thread
    _stop.set()
    t = _thread
    if t and t.is_alive() and t is not threading.current_thread():
        t.join(timeout=timeout)
    if t and not t.is_alive():
        _thread = None


def auto_sync_scheduler_running() -> bool:
    return bool(_thread and _thread.is_alive())
