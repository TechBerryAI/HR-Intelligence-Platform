"""Redis URL encoding, parse host, and no-secret error text (synthetic passwords only)."""
from __future__ import annotations

import importlib

import pytest

from app.config.env_validator import EnvValidator
from app.core.redis_url import canonicalize_redis_url, redis_endpoint_for_log, safe_redis_error


def test_unencoded_slash_in_password_parses_real_host():
    raw = 'redis://AAA/BBB=CCC@192.0.2.10:6379/0'
    canon = canonicalize_redis_url(raw)
    import redis

    kw = redis.ConnectionPool.from_url(canon).connection_kwargs
    assert kw['host'] == '192.0.2.10'
    assert kw['port'] == 6379
    assert int(kw.get('db') or 0) == 0
    assert kw['password'] == 'AAA/BBB=CCC'
    assert kw.get('username') in (None, '')
    assert 'AAA/BBB=CCC' not in canon
    assert '%2F' in canon


def test_already_encoded_password_is_not_double_encoded():
    raw = 'redis://:AAA%2FBBB%3DCCC@192.0.2.10:6379/0'
    canon = canonicalize_redis_url(raw)
    import redis

    kw = redis.ConnectionPool.from_url(canon).connection_kwargs
    assert kw['password'] == 'AAA/BBB=CCC'
    assert kw['host'] == '192.0.2.10'


def test_empty_user_colon_form():
    raw = 'redis://:simplepass@192.0.2.10:6379/1'
    canon = canonicalize_redis_url(raw)
    import redis

    kw = redis.ConnectionPool.from_url(canon).connection_kwargs
    assert kw['password'] == 'simplepass'
    assert kw['host'] == '192.0.2.10'
    assert int(kw.get('db') or 0) == 1


def test_no_auth_url_unchanged():
    raw = 'redis://192.0.2.10:6379/0'
    assert canonicalize_redis_url(raw) == raw


def test_rediss_and_user_password():
    raw = 'rediss://myuser:p@ss/word@192.0.2.10:6380/2'
    canon = canonicalize_redis_url(raw)
    assert canon.startswith('rediss://')
    import redis

    kw = redis.ConnectionPool.from_url(canon).connection_kwargs
    assert kw['host'] == '192.0.2.10'
    assert kw['password'] == 'p@ss/word'
    assert kw['username'] == 'myuser'


def test_endpoint_for_log_is_host_only():
    raw = 'redis://:SYNTHETIC_SECRET_PASS@192.0.2.10:6379/0'
    assert 'SYNTHETIC_SECRET_PASS' not in redis_endpoint_for_log(raw)
    assert '192.0.2.10' in redis_endpoint_for_log(raw)


def test_safe_redis_error_strips_url():
    exc = RuntimeError('Timeout connecting to redis://:SYNTHETIC_SECRET_PASS@192.0.2.10:6379/0')
    text = safe_redis_error(exc)
    assert 'SYNTHETIC_SECRET_PASS' not in text
    assert 'redis://:[REDACTED]@' in text or '[REDACTED]' in text


def test_ping_error_does_not_include_password():
    err = EnvValidator._ping_redis('redis://:SYNTHETIC_SECRET_PASS@127.0.0.1:1/0')
    assert err is not None
    assert 'SYNTHETIC_SECRET_PASS' not in err
    assert 'REDIS_URL' in err


def test_production_set_json_does_not_use_memory_when_redis_down(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'false')
    monkeypatch.setenv('REDIS_URL', 'redis://127.0.0.1:1/0')
    import app.core.shared_store as ss

    importlib.reload(ss)
    try:
        with pytest.raises(RuntimeError, match='Redis unavailable'):
            ss.set_json_nx('lease-key', {'owner': 't'}, 10)
        with pytest.raises(RuntimeError, match='Redis unavailable'):
            ss.set_json('oauth-key', {'hrid': 'H1'}, 10)
        assert ss.get_json('lease-key') is None
        assert ss.get_json('oauth-key') is None
        assert ss.rate_limit_hit('bucket', 5, 60) is True
    finally:
        monkeypatch.delenv('REDIS_URL', raising=False)
        importlib.reload(ss)


def test_dev_still_uses_memory_when_redis_down(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'true')
    monkeypatch.setenv('REDIS_URL', 'redis://127.0.0.1:1/0')
    import app.core.shared_store as ss

    importlib.reload(ss)
    try:
        ss.reset_memory_store_for_tests()
        assert ss.set_json_nx('dev-lease', {'owner': 't'}, 30) is True
        assert ss.get_json('dev-lease') == {'owner': 't'}
    finally:
        ss.reset_memory_store_for_tests()
        monkeypatch.delenv('REDIS_URL', raising=False)
        importlib.reload(ss)
