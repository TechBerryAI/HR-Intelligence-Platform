"""Background backup scheduler — starts once with the Flask app."""
from __future__ import annotations

import os
import threading
import time


_started = False
_lock = threading.Lock()


def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.getenv(name) or '').strip().lower()
    if not raw:
        return default
    return raw in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or '').strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def start_backup_scheduler() -> None:
    """Fire-and-forget: backup soon after boot if due, then every interval."""
    global _started
    if not _env_bool('BACKUP_ENABLED', True):
        print('[backup] scheduler off (BACKUP_ENABLED=false)')
        return
    with _lock:
        if _started:
            return
        _started = True

    interval_h = max(1, _env_int('BACKUP_INTERVAL_HOURS', 24))
    # Delay first check so DB pool / media init finish
    initial_delay_s = max(5, _env_int('BACKUP_STARTUP_DELAY_SECONDS', 30))

    def _loop() -> None:
        time.sleep(initial_delay_s)
        while True:
            try:
                from app.database.scripts.backup_hcip import needs_backup, run_backup

                if needs_backup(interval_hours=interval_h):
                    print('[backup] due — starting automatic backup')
                    run_backup(force=True)
                else:
                    print('[backup] not due yet')
            except Exception as exc:
                print(f'[backup] scheduler error: {exc}')
            time.sleep(interval_h * 3600)

    thread = threading.Thread(target=_loop, name='hcip-backup', daemon=True)
    thread.start()
    print(
        f'[backup] scheduler started (every {interval_h}h, '
        f'first check in {initial_delay_s}s)'
    )
