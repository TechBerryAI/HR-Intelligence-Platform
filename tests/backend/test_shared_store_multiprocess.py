"""Prove shared_store is process-local without Redis and shared with Redis.

These tests spawn fresh interpreters so module-level REDIS_URL is re-read.
They do not log secrets. Redis-enabled cases skip if local Redis is unreachable.
"""
from __future__ import annotations

import os
import uuid
from multiprocessing import get_context

import pytest

_SPAWN = get_context('spawn')


def _local_redis_url() -> str | None:
    url = (os.getenv('TEST_REDIS_URL') or os.getenv('REDIS_URL') or '').strip()
    candidates = [u for u in (url, 'redis://127.0.0.1:6380/15', 'redis://127.0.0.1:6379/15') if u]
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            import redis

            client = redis.Redis.from_url(
                candidate, decode_responses=True, socket_connect_timeout=1
            )
            client.ping()
            return candidate
        except Exception:
            continue
    return None


def _child_set_json(redis_url: str | None, key: str, value: dict) -> None:
    if redis_url:
        os.environ['REDIS_URL'] = redis_url
    else:
        os.environ.pop('REDIS_URL', None)
    import importlib

    import app.core.shared_store as ss

    importlib.reload(ss)
    ss.set_json(key, value, ttl_seconds=60)


def _child_pop_json(redis_url: str | None, key: str, q) -> None:
    if redis_url:
        os.environ['REDIS_URL'] = redis_url
    else:
        os.environ.pop('REDIS_URL', None)
    import importlib

    import app.core.shared_store as ss

    importlib.reload(ss)
    q.put(ss.pop_json(key))


def _child_rate_hits_after_barrier(redis_url: str, bucket: str, limit: int, n: int, start_evt, q) -> None:
    os.environ['REDIS_URL'] = redis_url
    os.environ['FLASK_DEBUG'] = 'true'
    import importlib

    import app.core.shared_store as ss

    importlib.reload(ss)
    start_evt.wait(timeout=15)
    limited = 0
    allowed = 0
    for _ in range(n):
        if ss.rate_limit_hit(bucket, limit, 60):
            limited += 1
        else:
            allowed += 1
    q.put({'allowed': allowed, 'limited': limited})


def _child_rate_hits(redis_url: str | None, bucket: str, limit: int, n: int, q) -> None:
    if redis_url:
        os.environ['REDIS_URL'] = redis_url
    else:
        os.environ.pop('REDIS_URL', None)
    import importlib

    import app.core.shared_store as ss

    importlib.reload(ss)
    limited = 0
    allowed = 0
    for _ in range(n):
        if ss.rate_limit_hit(bucket, limit, 60):
            limited += 1
        else:
            allowed += 1
    q.put({'allowed': allowed, 'limited': limited})


def test_oauth_state_not_visible_across_processes_without_redis():
    key = f'oauth:calendar:state:test-{uuid.uuid4().hex}'
    q = _SPAWN.Queue()
    a = _SPAWN.Process(target=_child_set_json, args=(None, key, {'hrid': 'H1', 'company_key': 'co'}))
    a.start()
    a.join(timeout=15)
    assert a.exitcode == 0
    b = _SPAWN.Process(target=_child_pop_json, args=(None, key, q))
    b.start()
    got = q.get(timeout=15)
    b.join(timeout=15)
    assert b.exitcode == 0
    assert got is None


def test_oauth_state_visible_across_processes_with_redis():
    url = _local_redis_url()
    if not url:
        pytest.skip('local Redis not reachable — OAuth Redis sharing NOT TESTABLE')
    key = f'oauth:calendar:state:test-{uuid.uuid4().hex}'
    q = _SPAWN.Queue()
    a = _SPAWN.Process(
        target=_child_set_json,
        args=(url, key, {'hrid': 'H1', 'company_key': 'co'}),
    )
    a.start()
    a.join(timeout=15)
    assert a.exitcode == 0
    b = _SPAWN.Process(target=_child_pop_json, args=(url, key, q))
    b.start()
    got = q.get(timeout=15)
    b.join(timeout=15)
    assert b.exitcode == 0
    assert got == {'hrid': 'H1', 'company_key': 'co'}


def test_rate_limit_is_per_process_without_redis():
    bucket = f'public_parse:test-{uuid.uuid4().hex}'
    q1 = _SPAWN.Queue()
    q2 = _SPAWN.Queue()
    p1 = _SPAWN.Process(target=_child_rate_hits, args=(None, bucket, 5, 5, q1))
    p2 = _SPAWN.Process(target=_child_rate_hits, args=(None, bucket, 5, 5, q2))
    p1.start()
    p1.join(timeout=15)
    p2.start()
    p2.join(timeout=15)
    r1 = q1.get(timeout=5)
    r2 = q2.get(timeout=5)
    assert r1['allowed'] == 5 and r1['limited'] == 0
    assert r2['allowed'] == 5 and r2['limited'] == 0


def test_rate_limit_is_global_with_redis():
    url = _local_redis_url()
    if not url:
        pytest.skip('local Redis not reachable — rate-limit Redis sharing NOT TESTABLE')
    bucket = f'public_parse:test-{uuid.uuid4().hex}'
    q1 = _SPAWN.Queue()
    q2 = _SPAWN.Queue()
    p1 = _SPAWN.Process(target=_child_rate_hits, args=(url, bucket, 5, 5, q1))
    p1.start()
    p1.join(timeout=15)
    r1 = q1.get(timeout=5)
    assert r1['allowed'] == 5
    p2 = _SPAWN.Process(target=_child_rate_hits, args=(url, bucket, 5, 5, q2))
    p2.start()
    p2.join(timeout=15)
    r2 = q2.get(timeout=5)
    assert r2['allowed'] == 0
    assert r2['limited'] == 5


def test_rate_limit_concurrent_cannot_exceed_limit():
    """Simultaneous workers must not exceed the Redis sliding-window limit."""
    url = _local_redis_url()
    if not url:
        pytest.skip('local Redis not reachable — concurrent rate-limit NOT TESTABLE')
    limit = 8
    workers = 4
    hits_each = 8
    bucket = f'public_parse:concurrent-{uuid.uuid4().hex}'
    start = _SPAWN.Event()
    queues = []
    procs = []
    for _ in range(workers):
        q = _SPAWN.Queue()
        p = _SPAWN.Process(
            target=_child_rate_hits_after_barrier,
            args=(url, bucket, limit, hits_each, start, q),
        )
        queues.append(q)
        procs.append(p)
        p.start()
    start.set()
    allowed = 0
    for q, p in zip(queues, procs):
        result = q.get(timeout=20)
        p.join(timeout=15)
        assert p.exitcode == 0
        allowed += result['allowed']
    assert allowed <= limit
    assert allowed >= 1
