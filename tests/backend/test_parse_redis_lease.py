"""Optional Redis SET NX parse lease — protocol tests with a fake shared store.

Two logical workers share KV state, not a dict of Futures. Live Redis is skipped
unless TEST_REDIS_URL is set.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser.engine.parse_inflight import run_or_join_shared
from app.core.shared_store import (
    delete_json_if_match,
    get_json,
    reset_memory_store_for_tests,
    set_json_nx,
)


class FakeSharedStore:
    """In-memory SET NX store shared by two logical workers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._kv: dict[str, tuple[dict, float | None]] = {}
        self.clock = time.time

    def _expired(self, exp: float | None) -> bool:
        return exp is not None and self.clock() > exp

    def set_json_nx(self, key: str, value: dict, ttl_seconds: int) -> bool:
        expires_at = (self.clock() + ttl_seconds) if ttl_seconds else None
        with self._lock:
            entry = self._kv.get(key)
            if entry and not self._expired(entry[1]):
                return False
            self._kv[key] = (value, expires_at)
            return True

    def set_json(self, key: str, value: dict, ttl_seconds: int | None = None) -> None:
        expires_at = (self.clock() + ttl_seconds) if ttl_seconds else None
        with self._lock:
            self._kv[key] = (value, expires_at)

    def get_json(self, key: str) -> dict | None:
        with self._lock:
            entry = self._kv.get(key)
            if not entry:
                return None
            value, exp = entry
            if self._expired(exp):
                self._kv.pop(key, None)
                return None
            return value

    def pop_json(self, key: str) -> dict | None:
        with self._lock:
            entry = self._kv.pop(key, None)
            if not entry:
                return None
            value, exp = entry
            if self._expired(exp):
                return None
            return value

    def delete_json_if_match(self, key: str, field: str, expected: str) -> bool:
        with self._lock:
            entry = self._kv.get(key)
            if not entry:
                return False
            value, exp = entry
            if self._expired(exp):
                self._kv.pop(key, None)
                return False
            if str(value.get(field)) != str(expected):
                return False
            self._kv.pop(key, None)
            return True


def test_set_json_nx_memory_reclaim():
    reset_memory_store_for_tests()
    assert set_json_nx('k', {'owner': 'a'}, ttl_seconds=1)
    assert not set_json_nx('k', {'owner': 'b'}, ttl_seconds=1)
    time.sleep(1.1)
    assert set_json_nx('k', {'owner': 'b'}, ttl_seconds=10)
    assert get_json('k')['owner'] == 'b'
    assert not delete_json_if_match('k', 'owner', 'a')
    assert delete_json_if_match('k', 'owner', 'b')
    assert get_json('k') is None
    reset_memory_store_for_tests()


def test_shared_one_owner_joiner_waits():
    store = FakeSharedStore()
    runs = []
    started = threading.Event()
    release = threading.Event()

    def work():
        started.set()
        release.wait(timeout=2)
        runs.append('owner')
        return {'status': 'ok'}, 200

    out = []

    def worker(label):
        out.append(
            (
                label,
                run_or_join_shared(
                    store,
                    'same-hash',
                    work if label == 'a' else lambda: (_ for _ in ()).throw(
                        RuntimeError('joiner must not run')
                    ),
                    lease_ttl=30,
                    result_ttl=30,
                    timeout=2,
                    poll=0.05,
                ),
            )
        )

    # Deterministic owner: pre-take the lease race by starting A first.
    t1 = threading.Thread(target=worker, args=('a',))
    t2 = threading.Thread(target=worker, args=('b',))
    t1.start()
    assert started.wait(timeout=2)
    t2.start()
    time.sleep(0.05)
    release.set()
    t1.join(timeout=3)
    t2.join(timeout=3)
    assert runs == ['owner']
    bodies = [result for _label, result in out]
    assert len(bodies) == 2
    assert all(result == ({'status': 'ok'}, 200) for result in bodies)


def test_shared_owner_failure_unblocks_retry():
    store = FakeSharedStore()

    def boom():
        raise RuntimeError('parse failed')

    with pytest.raises(RuntimeError, match='parse failed'):
        run_or_join_shared(store, 'fail-key', boom, lease_ttl=30, timeout=2, poll=0.05)

    # Lease must not be permanent — a later caller can own it.
    assert run_or_join_shared(
        store, 'fail-key', lambda: ({'status': 'ok'}, 200), lease_ttl=30, timeout=2, poll=0.05
    ) == ({'status': 'ok'}, 200)


def test_shared_expired_lease_reclaim():
    store = FakeSharedStore()
    assert store.set_json_nx('parse:lease:stale', {'owner': 'dead'}, ttl_seconds=1)
    time.sleep(1.1)
    ran = {'n': 0}

    def work():
        ran['n'] += 1
        return 'ok'

    assert run_or_join_shared(store, 'stale', work, lease_ttl=10, timeout=2, poll=0.05) == 'ok'
    assert ran['n'] == 1
    assert store.get_json('parse:lease:stale') is None


def test_non_owner_cannot_delete_lease():
    store = FakeSharedStore()
    assert store.set_json_nx('lease', {'owner': 'tok-a'}, ttl_seconds=30)
    assert not store.delete_json_if_match('lease', 'owner', 'tok-b')
    assert store.get_json('lease')['owner'] == 'tok-a'
    assert store.delete_json_if_match('lease', 'owner', 'tok-a')


@pytest.mark.skipif(not (os.getenv('TEST_REDIS_URL') or '').strip(), reason='TEST_REDIS_URL not set')
def test_live_redis_set_nx_optional():
    url = os.getenv('TEST_REDIS_URL', '').strip()
    os.environ['REDIS_URL'] = url
    import importlib

    import app.core.shared_store as ss

    importlib.reload(ss)
    key = f'test:parse:nx:{os.getpid()}'
    try:
        assert ss.set_json_nx(key, {'owner': 't1'}, ttl_seconds=10)
        assert not ss.set_json_nx(key, {'owner': 't2'}, ttl_seconds=10)
        assert ss.get_json(key)['owner'] == 't1'
        assert not ss.delete_json_if_match(key, 'owner', 'nope')
        assert ss.delete_json_if_match(key, 'owner', 't1')
    finally:
        ss.pop_json(key)
