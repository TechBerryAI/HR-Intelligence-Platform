"""Regression: auto-sync must not start once per Gunicorn web worker."""
from __future__ import annotations

import pytest

from app.domains.integrations import bootstrap
from app.domains.integrations.scheduler import (
    AUTO_SYNC_ADVISORY_LOCK_KEY,
    auto_sync_scheduler_running,
    release_auto_sync_lock,
    start_auto_sync_scheduler,
    stop_auto_sync_scheduler,
    tick_auto_sync,
    try_acquire_auto_sync_lock,
)


def test_init_integrations_does_not_start_auto_sync_by_default(monkeypatch):
    monkeypatch.delenv('RUN_INTEGRATION_AUTO_SYNC', raising=False)
    started = {'workers': False, 'sync': False}

    monkeypatch.setattr(
        'app.domains.integrations.provider.factory.ensure_default_providers',
        lambda: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.provider.calendar_factory.ensure_default_calendar_providers',
        lambda: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.events.subscribers.register_subscribers',
        lambda: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.worker.handlers.start_workers',
        lambda: started.__setitem__('workers', True),
    )
    monkeypatch.setattr(
        'app.domains.integrations.scheduler.start_auto_sync_scheduler',
        lambda: started.__setitem__('sync', True),
    )

    bootstrap.init_integrations()
    assert started['workers'] is True
    assert started['sync'] is False

    bootstrap.init_integrations()
    bootstrap.init_integrations()
    assert started['sync'] is False


def test_init_integrations_starts_auto_sync_when_flag_set(monkeypatch):
    monkeypatch.setenv('RUN_INTEGRATION_AUTO_SYNC', '1')
    started = {'sync': False}

    monkeypatch.setattr(
        'app.domains.integrations.provider.factory.ensure_default_providers',
        lambda: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.provider.calendar_factory.ensure_default_calendar_providers',
        lambda: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.events.subscribers.register_subscribers',
        lambda: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.worker.handlers.start_workers',
        lambda: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.scheduler.start_auto_sync_scheduler',
        lambda: started.__setitem__('sync', True),
    )

    bootstrap.init_integrations()
    assert started['sync'] is True


def test_start_stop_auto_sync_scheduler_lifecycle(monkeypatch):
    monkeypatch.setattr(
        'app.domains.integrations.scheduler.tick_auto_sync',
        lambda: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.scheduler.get_auto_sync_interval_seconds',
        lambda: 60,
    )
    stop_auto_sync_scheduler()
    assert auto_sync_scheduler_running() is False
    start_auto_sync_scheduler()
    assert auto_sync_scheduler_running() is True
    t1 = __import__('app.domains.integrations.scheduler', fromlist=['_thread'])._thread
    start_auto_sync_scheduler()
    t2 = __import__('app.domains.integrations.scheduler', fromlist=['_thread'])._thread
    assert t1 is t2
    stop_auto_sync_scheduler(timeout=2.0)
    assert auto_sync_scheduler_running() is False


def test_two_scheduler_ticks_only_one_runs_work(monkeypatch):
    """While A holds the advisory lock, B's tick must skip work."""
    from app.database.connection.db import _create_connection

    calls = {'n': 0}

    def fake_unlocked():
        calls['n'] += 1

    monkeypatch.setattr(
        'app.domains.integrations.scheduler._tick_auto_sync_unlocked',
        fake_unlocked,
    )

    try:
        conn_a = _create_connection()
    except Exception as exc:
        pytest.skip(f'Postgres unavailable for advisory-lock test: {exc}')

    try:
        assert try_acquire_auto_sync_lock(conn_a) is True
        conn_a.commit()

        ran_b = tick_auto_sync()
        assert ran_b is False
        assert calls['n'] == 0

        release_auto_sync_lock(conn_a)
        conn_a.commit()

        ran_a = tick_auto_sync()
        assert ran_a is True
        assert calls['n'] == 1
    finally:
        try:
            release_auto_sync_lock(conn_a)
            conn_a.commit()
        except Exception:
            pass
        try:
            conn_a.close()
        except Exception:
            pass


def test_advisory_lock_key_is_stable():
    assert AUTO_SYNC_ADVISORY_LOCK_KEY == 872_014_001
