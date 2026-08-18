"""
Shared key-value / rate-limit store.

Uses Redis when REDIS_URL is set and redis-py is importable. Process-local
memory is only for single-worker / local dev. Production with REDIS_URL set
never falls back to in-memory coordination.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import defaultdict, deque
from typing import Any

from app.core.redis_url import (
    canonicalize_redis_url,
    redis_endpoint_for_log,
    safe_redis_error,
)

logger = logging.getLogger(__name__)

_REDIS_URL = canonicalize_redis_url((os.getenv('REDIS_URL') or '').strip())
_redis_client = None
_redis_tried = False
_REDIS_UNAVAILABLE = 'Redis unavailable'

_mem_lock = threading.Lock()
_mem_kv: dict[str, tuple[Any, float | None]] = {}
_mem_hits: dict[str, deque] = defaultdict(deque)

# Atomic sliding-window: prune + check + add + expire in one EVAL.
_RATE_LIMIT_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = tonumber(redis.call('ZCARD', key))
if count >= limit then
  return 1
end
redis.call('ZADD', key, now, member)
local ttl = math.floor(window) + 1
if ttl < 1 then
  ttl = 1
end
redis.call('EXPIRE', key, ttl)
return 0
"""


def _production_like() -> bool:
    flask_debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    allow_insecure = os.getenv('ALLOW_INSECURE_JWT', 'false').lower() in (
        '1', 'true', 'yes', 'on',
    )
    return not flask_debug and not allow_insecure


def _reject_memory_fallback() -> bool:
    """REDIS_URL in production must not silently use process-local memory."""
    return bool(_REDIS_URL) and _production_like()


def _get_redis():
    global _redis_client, _redis_tried
    if not _REDIS_URL:
        return None
    if _redis_client is not None:
        return _redis_client
    if _redis_tried and not _production_like():
        return None
    _redis_tried = True
    try:
        import redis

        client = redis.Redis.from_url(
            _REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        logger.info(
            '[shared_store] Redis connected (%s)',
            redis_endpoint_for_log(_REDIS_URL),
        )
    except Exception as exc:
        _redis_client = None
        err = safe_redis_error(exc)
        if _production_like():
            logger.error('[shared_store] Redis unavailable in production (%s)', err)
            _redis_tried = False
        else:
            logger.warning(
                '[shared_store] Redis unavailable (%s); using in-memory store', err
            )
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


# Compact and spaced JSON both appear depending on dumps separators.
_OWNER_NEEDLE_LUA = """
local function owner_match(raw, token)
  local a = '"owner":"' .. token .. '"'
  local b = '"owner": "' .. token .. '"'
  return string.find(raw, a, 1, true) or string.find(raw, b, 1, true)
end
"""

_DELETE_IF_MATCH_LUA = _OWNER_NEEDLE_LUA + """
local raw = redis.call('GET', KEYS[1])
if not raw then
  return 0
end
if owner_match(raw, ARGV[1]) then
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
"""

_RENEW_IF_MATCH_LUA = _OWNER_NEEDLE_LUA + """
local raw = redis.call('GET', KEYS[1])
if not raw then
  return 0
end
if owner_match(raw, ARGV[1]) then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
  return 1
end
return 0
"""


def reset_memory_store_for_tests() -> None:
    with _mem_lock:
        _mem_kv.clear()
        _mem_hits.clear()


def set_json_nx(key: str, value: dict, ttl_seconds: int) -> bool:
    """Atomic set-if-not-exists. Returns True if this caller created the key."""
    payload = json.dumps(value)
    ttl = int(ttl_seconds) if ttl_seconds else 0
    client = _get_redis()
    if client is not None:
        try:
            kwargs: dict[str, Any] = {'nx': True}
            if ttl > 0:
                kwargs['ex'] = ttl
            return bool(client.set(key, payload, **kwargs))
        except Exception as exc:
            logger.warning(
                '[shared_store] set_json_nx Redis error: %s', safe_redis_error(exc)
            )
            if _production_like():
                raise
            return False
    if _reject_memory_fallback():
        raise RuntimeError(_REDIS_UNAVAILABLE)
    expires_at = (time.time() + ttl) if ttl > 0 else None
    now = time.time()
    with _mem_lock:
        entry = _mem_kv.get(key)
        if entry:
            _value, exp = entry
            if exp is None or now <= exp:
                return False
            _mem_kv.pop(key, None)
        _mem_kv[key] = (value, expires_at)
        return True


def renew_json_if_match(key: str, field: str, expected: str, ttl_seconds: int) -> bool:
    """Extend TTL only when stored JSON ``field`` still equals ``expected``. Never recreates the key."""
    ttl = int(ttl_seconds) if ttl_seconds else 0
    if ttl <= 0:
        return False
    client = _get_redis()
    if client is not None:
        try:
            renewed = client.eval(_RENEW_IF_MATCH_LUA, 1, key, str(expected), ttl)
            return int(renewed) == 1
        except Exception as exc:
            logger.warning(
                '[shared_store] renew_json_if_match Redis error: %s',
                safe_redis_error(exc),
            )
            raise
    if _reject_memory_fallback():
        return False
    now = time.time()
    with _mem_lock:
        entry = _mem_kv.get(key)
        if not entry:
            return False
        value, expires_at = entry
        if expires_at is not None and now > expires_at:
            _mem_kv.pop(key, None)
            return False
        if not isinstance(value, dict) or str(value.get(field)) != str(expected):
            return False
        _mem_kv[key] = (value, now + ttl)
        return True


def delete_json_if_match(key: str, field: str, expected: str) -> bool:
    """Delete key only when stored JSON ``field`` still equals ``expected``."""
    client = _get_redis()
    if client is not None:
        try:
            deleted = client.eval(_DELETE_IF_MATCH_LUA, 1, key, str(expected))
            return int(deleted) == 1
        except Exception as exc:
            logger.warning(
                '[shared_store] delete_json_if_match Redis error: %s',
                safe_redis_error(exc),
            )
            return False
    if _reject_memory_fallback():
        return False
    now = time.time()
    with _mem_lock:
        entry = _mem_kv.get(key)
        if not entry:
            return False
        value, expires_at = entry
        if expires_at is not None and now > expires_at:
            _mem_kv.pop(key, None)
            return False
        if not isinstance(value, dict) or str(value.get(field)) != str(expected):
            return False
        _mem_kv.pop(key, None)
        return True


def set_json(key: str, value: dict, ttl_seconds: int | None = None) -> None:
    client = _get_redis()
    payload = json.dumps(value)
    if client is not None:
        try:
            if ttl_seconds and ttl_seconds > 0:
                client.setex(key, int(ttl_seconds), payload)
            else:
                client.set(key, payload)
            return
        except Exception as exc:
            logger.warning(
                '[shared_store] set_json Redis error: %s', safe_redis_error(exc)
            )
            if _production_like():
                raise
    if _reject_memory_fallback():
        raise RuntimeError(_REDIS_UNAVAILABLE)
    expires_at = (time.time() + ttl_seconds) if ttl_seconds and ttl_seconds > 0 else None
    with _mem_lock:
        _mem_kv[key] = (value, expires_at)


def get_json(key: str) -> dict | None:
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(key)
        except Exception as exc:
            logger.warning(
                '[shared_store] get_json Redis error: %s', safe_redis_error(exc)
            )
            return None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (TypeError, json.JSONDecodeError):
            return None
    if _reject_memory_fallback():
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
        try:
            try:
                raw = client.getdel(key)
            except Exception:
                pipe = client.pipeline()
                pipe.get(key)
                pipe.delete(key)
                raw, _ = pipe.execute()
        except Exception as exc:
            logger.warning(
                '[shared_store] pop_json Redis error: %s', safe_redis_error(exc)
            )
            return None
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (TypeError, json.JSONDecodeError):
            return None
    if _reject_memory_fallback():
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
        member = f'{now}:{os.getpid()}:{id(object())}'
        try:
            limited = client.eval(
                _RATE_LIMIT_LUA,
                1,
                bucket_key,
                now,
                window_sec,
                limit,
                member,
            )
            return int(limited) == 1
        except Exception as exc:
            logger.warning(
                '[shared_store] rate_limit Redis error: %s', safe_redis_error(exc)
            )
            # Fail closed for this request when Redis was the configured store.
            return True

    if _reject_memory_fallback():
        return True

    with _mem_lock:
        q = _mem_hits[bucket_key]
        while q and now - q[0] > window_sec:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False
