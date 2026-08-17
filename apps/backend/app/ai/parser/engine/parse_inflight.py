"""Process-local in-flight parse join (stream fallback must not duplicate work).

Keyed by content hash + document kind + cache tag. Short TTL, bounded size.
Does not share persistent DB TOON across public uploaders.
Gunicorn multi-worker: join is in-process only.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')

_LOCK = threading.Lock()
_INFLIGHT: dict[str, Future] = {}
_RECENT: dict[str, tuple[Any, float]] = {}
_MAX_ENTRIES = 64
_TTL_SEC = 90.0


def inflight_key(file_hash: str, kind: str, cache_tag: str) -> str:
    return f'{cache_tag}:{kind}:{file_hash}'


def reset_parse_inflight_for_tests() -> None:
    with _LOCK:
        _INFLIGHT.clear()
        _RECENT.clear()


def _prune_locked(now: float) -> None:
    stale = [k for k, (_val, exp) in _RECENT.items() if exp <= now]
    for k in stale:
        _RECENT.pop(k, None)
    while len(_RECENT) > _MAX_ENTRIES:
        oldest = min(_RECENT.items(), key=lambda kv: kv[1][1])
        _RECENT.pop(oldest[0], None)


def run_or_join(key: str, fn: Callable[[], T], *, ttl_sec: float = _TTL_SEC) -> T:
    """Run fn once per key; concurrent callers wait; success is reused briefly."""
    created = False
    fut: Optional[Future] = None
    now = time.time()
    with _LOCK:
        _prune_locked(now)
        recent = _RECENT.get(key)
        if recent is not None:
            value, expiry = recent
            if expiry > now:
                logger.debug('parse inflight recent-hit key=%s', key)
                return value
            _RECENT.pop(key, None)
        fut = _INFLIGHT.get(key)
        if fut is None:
            fut = Future()
            _INFLIGHT[key] = fut
            created = True

    if not created:
        logger.debug('parse inflight join key=%s', key)
        return fut.result()

    try:
        result = fn()
        fut.set_result(result)
        with _LOCK:
            _RECENT[key] = (result, time.time() + ttl_sec)
            _INFLIGHT.pop(key, None)
            _prune_locked(time.time())
        return result
    except Exception as exc:
        fut.set_exception(exc)
        with _LOCK:
            _INFLIGHT.pop(key, None)
            _RECENT.pop(key, None)
        raise
