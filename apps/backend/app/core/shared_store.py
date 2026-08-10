"""
Shared key-value / rate-limit store.

Uses Redis when REDIS_URL is set and redis-py is importable; otherwise falls
back to process-local memory (fine for single-worker / local dev).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger(__name__)

_REDIS_URL = (os.getenv('REDIS_URL') or '').strip()
_redis_client = None
_redis_tried = False

_mem_lock = threading.Lock()
_mem_kv: dict[str, tuple[Any, float | None]] = {}
_mem_hits: dict[str, deque] = defaultdict(deque)


def _get_redis():
    global _redis_client, _redis_tried
    if not _REDIS_URL:
        return None
    if _redis_tried:
        return _redis_client
    _redis_tried = True
    try:
        import redis

        client = redis.Redis.from_url(_REDIS_URL, decode_responses=True)
        client.ping()
        _redis_client = client
        logger.info('[shared_store] Redis connected (%s)', _REDIS_URL.split('@')[-1])
    except Exception as exc:
        logger.warning('[shared_store] Redis unavailable (%s); using in-memory store', exc)
        _redis_client = None
    return _redis_client


def redis_status() -> str:
    """Return 'ok', 'error', or 'not_configured' for health checks."""
    if not _REDIS_URL:
        return 'not_configured'
    client = _get_redis()
    if client is None:
        return 'error'
    try:
        client.ping()
        return 'ok'
    except Exception:
        return 'error'


def set_json(key: str, value: dict, ttl_seconds: int | None = None) -> None:
    client = _get_redis()
    payload = json.dumps(value)
    if client is not None:
        if ttl_seconds and ttl_seconds > 0:
            client.setex(key, int(ttl_seconds), payload)
        else:
            client.set(key, payload)
        return
    expires_at = (time.time() + ttl_seconds) if ttl_seconds and ttl_seconds > 0 else None
    with _mem_lock:
        _mem_kv[key] = (value, expires_at)


def get_json(key: str) -> dict | None:
    client = _get_redis()
    if client is not None:
        raw = client.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (TypeError, json.JSONDecodeError):
            return None
    with _mem_lock:
        entry = _mem_kv.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at is not None and time.time() > expires_at:
            _mem_kv.pop(key, None)
            return None
        return value if isinstance(value, dict) else None


def pop_json(key: str) -> dict | None:
    client = _get_redis()
    if client is not None:
        # GETDEL if available (Redis 6.2+); else GET + DEL
        try:
            raw = client.getdel(key)
        except Exception:
            pipe = client.pipeline()
            pipe.get(key)
            pipe.delete(key)
            raw, _ = pipe.execute()
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (TypeError, json.JSONDecodeError):
            return None
    with _mem_lock:
        entry = _mem_kv.pop(key, None)
        if not entry:
            return None
        value, expires_at = entry
        if expires_at is not None and time.time() > expires_at:
            return None
        return value if isinstance(value, dict) else None


def rate_limit_hit(bucket_key: str, limit: int, window_sec: int) -> bool:
    """
    Record one hit for bucket_key. Return True if the caller is over the limit
    (hit is not recorded when already limited).
    """
    if limit <= 0:
        return False
    now = time.time()
    client = _get_redis()
    if client is not None:
        # Sliding window via sorted set of timestamps
        cutoff = now - window_sec
        pipe = client.pipeline()
        pipe.zremrangebyscore(bucket_key, 0, cutoff)
        pipe.zcard(bucket_key)
        _, count = pipe.execute()
        if int(count) >= limit:
            return True
        member = f'{now}:{os.getpid()}:{id(object())}'
        pipe = client.pipeline()
        pipe.zadd(bucket_key, {member: now})
        pipe.expire(bucket_key, max(int(window_sec) + 1, 1))
        pipe.execute()
        return False

    with _mem_lock:
        q = _mem_hits[bucket_key]
        while q and now - q[0] > window_sec:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False
