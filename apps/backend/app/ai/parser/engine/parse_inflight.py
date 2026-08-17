"""In-flight parse join so stream fallback must not duplicate work.

Keyed by content hash + document kind + cache tag. Short TTL, bounded size.
Does not share persistent DB TOON across public uploaders.

Same-process callers join a Future. When Redis is up (``redis_status()=='ok'``),
an additional SET NX lease coordinates the same key across Gunicorn workers.
Without Redis, join is per process only — a documented multi-worker limitation.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future
from typing import Any, Callable, Optional, Protocol, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')

_LOCK = threading.Lock()
_INFLIGHT: dict[str, Future] = {}
_RECENT: dict[str, tuple[Any, float]] = {}
_MAX_ENTRIES = 64
_TTL_SEC = 90.0

LEASE_TTL_SEC = 180
RESULT_TTL_SEC = 90
JOIN_TIMEOUT_SEC = 180
JOIN_POLL_SEC = 0.1


class SharedKV(Protocol):
    def set_json_nx(self, key: str, value: dict, ttl_seconds: int) -> bool: ...
    def set_json(self, key: str, value: dict, ttl_seconds: int | None = None) -> None: ...
    def get_json(self, key: str) -> dict | None: ...
    def pop_json(self, key: str) -> dict | None: ...
    def delete_json_if_match(self, key: str, field: str, expected: str) -> bool: ...


def inflight_key(file_hash: str, kind: str, cache_tag: str) -> str:
    return f'{cache_tag}:{kind}:{file_hash}'


def lease_key(key: str) -> str:
    return f'parse:lease:{key}'


def result_key(key: str) -> str:
    return f'parse:result:{key}'


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


def _cross_worker_enabled() -> bool:
    try:
        from app.core.shared_store import redis_status

        return redis_status() == 'ok'
    except Exception:
        return False


def _pack_result(result: Any) -> dict[str, Any]:
    if isinstance(result, tuple) and len(result) == 2:
        body, status = result
        return {'ok': True, 'body': body, 'status': status, 'tuple': True}
    return {'ok': True, 'body': result, 'status': None, 'tuple': False}


def _unpack_result(data: dict[str, Any]) -> Any:
    if data.get('tuple'):
        return data.get('body'), data.get('status')
    return data.get('body')


def run_or_join_shared(
    store: SharedKV,
    key: str,
    fn: Callable[[], T],
    *,
    lease_ttl: int = LEASE_TTL_SEC,
    result_ttl: int = RESULT_TTL_SEC,
    timeout: float = JOIN_TIMEOUT_SEC,
    poll: float = JOIN_POLL_SEC,
    owner_token: str | None = None,
) -> T:
    """Cross-worker join via SET NX lease. Independent of in-process Futures."""
    token = owner_token or uuid.uuid4().hex
    lkey = lease_key(key)
    rkey = result_key(key)
    if store.set_json_nx(lkey, {'owner': token}, lease_ttl):
        try:
            store.pop_json(rkey)
            result = fn()
            store.set_json(rkey, _pack_result(result), result_ttl)
            return result
        except Exception as exc:
            try:
                store.set_json(rkey, {'ok': False, 'error': str(exc)}, result_ttl)
            except Exception:
                logger.warning('parse lease: failed to store error for key=%s', key)
            raise
        finally:
            store.delete_json_if_match(lkey, 'owner', token)

    deadline = time.time() + timeout
    while time.time() < deadline:
        data = store.get_json(rkey)
        if data:
            if data.get('ok') is True:
                return _unpack_result(data)
            raise RuntimeError(data.get('error') or 'parse failed')
        time.sleep(max(0.05, poll))
    raise TimeoutError(f'parse join timed out key={key}')


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
        if _cross_worker_enabled():
            from app.core import shared_store as store

            result = run_or_join_shared(store, key, fn)
        else:
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
