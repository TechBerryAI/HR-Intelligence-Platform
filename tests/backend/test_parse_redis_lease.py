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

from app.ai.parser.engine.parse_inflight import (
    LeaseHeartbeat,
    lease_heartbeat_threads_for_tests,
    lease_key,
    reset_parse_inflight_for_tests,
    run_or_join_shared,
)
from app.core.shared_store import (
    delete_json_if_match,
    get_json,
    renew_json_if_match,
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

    def renew_json_if_match(self, key: str, field: str, expected: str, ttl_seconds: int) -> bool:
        expires_at = (self.clock() + ttl_seconds) if ttl_seconds else None
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
            self._kv[key] = (value, expires_at)
            return True


def setup_function():
    reset_parse_inflight_for_tests()


def teardown_function():
    reset_parse_inflight_for_tests()


def _assert_no_heartbeats():
    leftover = lease_heartbeat_threads_for_tests()
    assert leftover == [], leftover


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


def test_memory_renew_only_if_owner():
    reset_memory_store_for_tests()
    assert set_json_nx('rk', {'owner': 'tok-a'}, ttl_seconds=2)
    assert renew_json_if_match('rk', 'owner', 'tok-a', 10)
    assert not renew_json_if_match('rk', 'owner', 'tok-b', 10)
    time.sleep(0.05)
    assert get_json('rk')['owner'] == 'tok-a'
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
                    renew_interval=15,
                ),
            )
        )

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
    _assert_no_heartbeats()


def test_shared_owner_failure_unblocks_retry():
    store = FakeSharedStore()

    def boom():
        raise RuntimeError('parse failed')

    with pytest.raises(RuntimeError, match='parse failed'):
        run_or_join_shared(
            store, 'fail-key', boom, lease_ttl=30, timeout=2, poll=0.05, renew_interval=15
        )
    _assert_no_heartbeats()

    assert run_or_join_shared(
        store,
        'fail-key',
        lambda: ({'status': 'ok'}, 200),
        lease_ttl=30,
        timeout=2,
        poll=0.05,
        renew_interval=15,
    ) == ({'status': 'ok'}, 200)
    _assert_no_heartbeats()


def test_heartbeat_stops_after_exception():
    store = FakeSharedStore()

    def boom():
        raise RuntimeError('explode')

    with pytest.raises(RuntimeError, match='explode'):
        run_or_join_shared(
            store, 'exc-key', boom, lease_ttl=30, timeout=2, poll=0.05, renew_interval=15
        )
    _assert_no_heartbeats()


def test_shared_expired_lease_reclaim():
    store = FakeSharedStore()
    assert store.set_json_nx('parse:lease:stale', {'owner': 'dead'}, ttl_seconds=1)
    time.sleep(1.1)
    ran = {'n': 0}

    def work():
        ran['n'] += 1
        return 'ok'

    assert run_or_join_shared(
        store, 'stale', work, lease_ttl=10, timeout=2, poll=0.05, renew_interval=15
    ) == 'ok'
    assert ran['n'] == 1
    assert store.get_json('parse:lease:stale') is None
    _assert_no_heartbeats()


def test_non_owner_cannot_delete_lease():
    store = FakeSharedStore()
    assert store.set_json_nx('lease', {'owner': 'tok-a'}, ttl_seconds=30)
    assert not store.delete_json_if_match('lease', 'owner', 'tok-b')
    assert store.get_json('lease')['owner'] == 'tok-a'
    assert store.delete_json_if_match('lease', 'owner', 'tok-a')


def test_old_owner_cannot_renew_or_delete_new_owner():
    store = FakeSharedStore()
    assert store.set_json_nx('lease', {'owner': 'tok-a'}, ttl_seconds=30)
    store.set_json('lease', {'owner': 'tok-b'}, ttl_seconds=30)
    assert not store.renew_json_if_match('lease', 'owner', 'tok-a', 30)
    assert store.renew_json_if_match('lease', 'owner', 'tok-b', 30)
    assert not store.delete_json_if_match('lease', 'owner', 'tok-a')
    assert store.get_json('lease')['owner'] == 'tok-b'
    assert store.delete_json_if_match('lease', 'owner', 'tok-b')


def test_heartbeat_retains_ownership_past_original_ttl():
    store = FakeSharedStore()
    runs = []
    started = threading.Event()

    def owner_work():
        started.set()
        time.sleep(2.4)
        runs.append('owner')
        return 'ok'

    def joiner_work():
        runs.append('joiner')
        return 'dup'

    out = []

    def worker(label):
        fn = owner_work if label == 'a' else joiner_work
        out.append(
            run_or_join_shared(
                store,
                'long-parse',
                fn,
                lease_ttl=2,
                result_ttl=5,
                timeout=4,
                poll=0.05,
                renew_interval=0.25,
            )
        )

    t1 = threading.Thread(target=worker, args=('a',))
    t2 = threading.Thread(target=worker, args=('b',))
    t1.start()
    assert started.wait(timeout=2)
    time.sleep(0.4)
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert runs == ['owner']
    assert out == ['ok', 'ok']
    _assert_no_heartbeats()


def test_stale_owner_recoverable_after_heartbeat_stop():
    store = FakeSharedStore()
    lkey = lease_key('crash')
    token = 'tok-dead'
    assert store.set_json_nx(lkey, {'owner': token}, ttl_seconds=2)
    hb = LeaseHeartbeat(store, lkey, token, 2, 0.25)
    hb.start()
    time.sleep(0.4)
    assert hb.renew_count >= 1
    hb.stop()
    _assert_no_heartbeats()
    time.sleep(2.2)
    ran = {'n': 0}

    def work():
        ran['n'] += 1
        return 'reclaimed'

    assert run_or_join_shared(
        store, 'crash', work, lease_ttl=10, timeout=2, poll=0.05, renew_interval=15
    ) == 'reclaimed'
    assert ran['n'] == 1
    _assert_no_heartbeats()


def test_renew_errors_do_not_deadlock():
    class BoomRenew(FakeSharedStore):
        def renew_json_if_match(self, *a, **k):
            raise RuntimeError('redis down')

    store = BoomRenew()
    t0 = time.time()
    assert run_or_join_shared(
        store,
        'boom-renew',
        lambda: 'ok',
        lease_ttl=30,
        timeout=3,
        poll=0.05,
        renew_interval=0.05,
    ) == 'ok'
    assert time.time() - t0 < 3
    _assert_no_heartbeats()


@pytest.mark.skipif(not (os.getenv('TEST_REDIS_URL') or '').strip(), reason='TEST_REDIS_URL not set')
def test_live_redis_set_nx_optional():
    url = os.getenv('TEST_REDIS_URL', '').strip()
    os.environ['REDIS_URL'] = url
    import importlib

    import app.core.shared_store as ss

    importlib.reload(ss)
    key = f'test:parse:nx:{os.getpid()}'
    expire_key = f'test:parse:ttl:{os.getpid()}'
    try:
        assert ss.set_json_nx(key, {'owner': 't1'}, ttl_seconds=30)
        assert not ss.set_json_nx(key, {'owner': 't2'}, ttl_seconds=30)
        assert ss.get_json(key)['owner'] == 't1'
        assert ss.renew_json_if_match(key, 'owner', 't1', 30)
        assert not ss.renew_json_if_match(key, 'owner', 't2', 30)
        assert not ss.delete_json_if_match(key, 'owner', 'nope')
        assert ss.delete_json_if_match(key, 'owner', 't1')
        assert ss.set_json_nx(expire_key, {'owner': 'old'}, ttl_seconds=1)
        time.sleep(1.2)
        assert ss.set_json_nx(expire_key, {'owner': 'new'}, ttl_seconds=10)
        assert ss.get_json(expire_key)['owner'] == 'new'
        assert ss.delete_json_if_match(expire_key, 'owner', 'new')
    finally:
        ss.pop_json(key)
        ss.pop_json(expire_key)
