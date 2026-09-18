"""In-flight parse join so stream fallback must not duplicate work.

Keyed by content hash + document kind + cache tag. Short TTL, bounded size.
Does not share persistent DB TOON across public uploaders.

Same-process callers join a Future. When Redis is up (``redis_status()=='ok'``),
an additional SET NX lease coordinates the same key across Gunicorn workers.
The owner renews the lease on a heartbeat until success/failure/exception.
Without Redis, join is per process only.
"""
from __future__ import annotations

import logging
import os
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
JOIN_POLL_SEC = 0.1
_HEARTBEAT_JOIN_SEC = 2.0
_RENEW_RETRIES = 3
_RENEW_RETRY_WAIT_SEC = 0.2

_HEARTBEAT_LOCK = threading.Lock()
_HEARTBEATS: set[threading.Thread] = set()


class SharedKV(Protocol):
    def set_json_nx(self, key: str, value: dict, ttl_seconds: int) -> bool: ...
    def set_json(self, key: str, value: dict, ttl_seconds: int | None = None) -> None: ...
    def get_json(self, key: str) -> dict | None: ...
    def pop_json(self, key: str) -> dict | None: ...
    def delete_json_if_match(self, key: str, field: str, expected: str) -> bool: ...
    def renew_json_if_match(self, key: str, field: str, expected: str, ttl_seconds: int) -> bool: ...


def inflight_key(file_hash: str, kind: str, cache_tag: str) -> str:
    return f'{cache_tag}:{kind}:{file_hash}'


def lease_key(key: str) -> str:
    return f'parse:lease:{key}'


def result_key(key: str) -> str:
    return f'parse:result:{key}'


def join_timeout_sec() -> float:
    raw = (os.getenv('GUNICORN_TIMEOUT') or '').strip()
    try:
        if raw:
            return max(1.0, float(raw))
    except ValueError:
        pass
    return 320.0


def renew_interval_sec(lease_ttl: int) -> float:
    """Leave margin before expiry; tests pass a shorter interval explicitly."""
    ttl = max(1, int(lease_ttl))
    return max(15.0, ttl / 3.0)


def lease_heartbeat_threads_for_tests() -> list[threading.Thread]:
    with _HEARTBEAT_LOCK:
        return [t for t in _HEARTBEATS if t.is_alive()]


def reset_parse_inflight_for_tests() -> None:
    with _LOCK:
        _INFLIGHT.clear()
        _RECENT.clear()
    with _HEARTBEAT_LOCK:
        leftover = list(_HEARTBEATS)
        _HEARTBEATS.clear()
    for thread in leftover:
        thread.join(timeout=_HEARTBEAT_JOIN_SEC)


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


def _worker_count() -> int:
    raw = (os.getenv('GUNICORN_WORKERS') or '').strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    software = (os.getenv('SERVER_SOFTWARE') or '').lower()
    if software.startswith('gunicorn'):
        return 4
    return 1


def _redis_coordination_required() -> bool:
    """REDIS_URL plus multiple workers means in-process join is not a safe fallback."""
    if not (os.getenv('REDIS_URL') or '').strip():
        return False
    return _worker_count() > 1


def _pack_result(result: Any) -> dict[str, Any]:
    if isinstance(result, tuple) and len(result) == 2:
        body, status = result
        return {'ok': True, 'body': body, 'status': status, 'tuple': True}
    return {'ok': True, 'body': result, 'status': None, 'tuple': False}


def _unpack_result(data: dict[str, Any]) -> Any:
    if data.get('tuple'):
        return data.get('body'), data.get('status')
    return data.get('body')


class LeaseHeartbeat:
    """One daemon thread: renew lease while this token still owns it."""

    def __init__(
        self,
        store: SharedKV,
        key: str,
        token: str,
        ttl: int,
        interval: float,
        *,
        renew_retries: int = _RENEW_RETRIES,
    ) -> None:
        self.store = store
        self.key = key
        self.token = token
        self.ttl = ttl
        self.interval = max(0.05, float(interval))
        self.renew_retries = max(1, int(renew_retries))
        self._stop = threading.Event()
        self.ownership_lost = threading.Event()
        self.renew_count = 0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        thread = threading.Thread(target=self._loop, name='parse-lease-hb', daemon=True)
        self._thread = thread
        with _HEARTBEAT_LOCK:
            _HEARTBEATS.add(thread)
        thread.start()

    def stop(self, join_timeout: float = _HEARTBEAT_JOIN_SEC) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=join_timeout)
            with _HEARTBEAT_LOCK:
                _HEARTBEATS.discard(thread)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            if not self._renew_with_retries():
                self.ownership_lost.set()
                logger.warning('parse lease: ownership lost or renew failed key=%s', self.key)
                return

    def _renew_with_retries(self) -> bool:
        for attempt in range(self.renew_retries):
            try:
                ok = self.store.renew_json_if_match(self.key, 'owner', self.token, self.ttl)
                if ok:
                    self.renew_count += 1
                    return True
                return False
            except Exception as exc:
                logger.warning(
                    'parse lease renew error key=%s attempt=%s: %s',
                    self.key,
                    attempt + 1,
                    exc,
                )
                if attempt + 1 >= self.renew_retries:
                    return False
                if self._stop.wait(_RENEW_RETRY_WAIT_SEC):
                    return True
        return False


def run_or_join_shared(
    store: SharedKV,
    key: str,
    fn: Callable[[], T],
    *,
    lease_ttl: int = LEASE_TTL_SEC,
    result_ttl: int = RESULT_TTL_SEC,
    timeout: float | None = None,
    poll: float = JOIN_POLL_SEC,
    owner_token: str | None = None,
    renew_interval: float | None = None,
) -> T:
    """Cross-worker join via SET NX lease. Independent of in-process Futures."""
    token = owner_token or uuid.uuid4().hex
    lkey = lease_key(key)
    rkey = result_key(key)
    wait = timeout if timeout is not None else join_timeout_sec()
    interval = renew_interval if renew_interval is not None else renew_interval_sec(lease_ttl)
    if store.set_json_nx(lkey, {'owner': token}, lease_ttl):
        heartbeat = LeaseHeartbeat(store, lkey, token, lease_ttl, interval)
        lost = False
        try:
            heartbeat.start()
            store.pop_json(rkey)
            result = fn()
            lost = heartbeat.ownership_lost.is_set()
            if not lost:
                store.set_json(rkey, _pack_result(result), result_ttl)
            return result
        except Exception as exc:
            lost = heartbeat.ownership_lost.is_set()
            if not lost:
                try:
                    store.set_json(rkey, {'ok': False, 'error': type(exc).__name__}, result_ttl)
                except Exception:
                    logger.warning('parse lease: failed to store error for key=%s', key)
            raise
        finally:
            heartbeat.stop()
            if not heartbeat.ownership_lost.is_set():
                store.delete_json_if_match(lkey, 'owner', token)

    deadline = time.time() + wait
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
        return fut.result(timeout=join_timeout_sec())

    try:
        if _cross_worker_enabled():
            from app.core import shared_store as store

            result = run_or_join_shared(store, key, fn)
        elif _redis_coordination_required():
            raise RuntimeError('Redis parse coordination unavailable')
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
