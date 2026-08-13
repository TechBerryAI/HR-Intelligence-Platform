"""Production fail-closed configuration (no live app import)."""
from __future__ import annotations

import pytest

from app.config.env_validator import EnvValidator
from app.core.auth import _resolve_jwt_secret


def _prod_base(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'false')
    monkeypatch.setenv('DEVELOPER_MODE', 'false')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost:5432/hrms')
    monkeypatch.setenv('JWT_SECRET', 'production-unique-jwt-secret-at-least-32ch')
    monkeypatch.setenv('INTEGRATION_SECRETS_KEY', 'unit-test-integration-secrets-key-32b')
    monkeypatch.delenv('GOOGLE_OAUTH_CLIENT_ID', raising=False)
    monkeypatch.delenv('REDIS_URL', raising=False)
    monkeypatch.delenv('GUNICORN_WORKERS', raising=False)
    monkeypatch.delenv('N8N_WEBHOOK_URL', raising=False)
    monkeypatch.delenv('SERVER_SOFTWARE', raising=False)


def test_production_ok_without_redis_single_worker(monkeypatch):
    _prod_base(monkeypatch)
    ok, errors, _ = EnvValidator.validate()
    assert ok, errors


def test_production_rejects_placeholder_jwt(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('JWT_SECRET', 'replace-with-a-unique-secret-at-least-32-chars')
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('JWT_SECRET' in e for e in errors)


def test_production_rejects_short_jwt(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('JWT_SECRET', 'too-short')
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('JWT_SECRET' in e for e in errors)


def test_production_rejects_empty_jwt(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('JWT_SECRET', '   ')
    ok, errors, _ = EnvValidator.validate()
    assert not ok


def test_resolve_jwt_secret_rejects_example_in_production(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'false')
    monkeypatch.setenv('JWT_SECRET', 'replace-with-a-unique-secret-at-least-32-chars')
    with pytest.raises(RuntimeError):
        _resolve_jwt_secret()


def test_production_requires_integration_secrets_key(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.delenv('INTEGRATION_SECRETS_KEY', raising=False)
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('INTEGRATION_SECRETS_KEY' in e for e in errors)


def test_production_rejects_dev_integration_key(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('INTEGRATION_SECRETS_KEY', 'dev-integration-secrets')
    ok, errors, _ = EnvValidator.validate()
    assert not ok


def test_production_rejects_developer_mode(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('DEVELOPER_MODE', 'true')
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('DEVELOPER_MODE' in e for e in errors)


def test_gunicorn_rejects_flask_debug(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'true')
    monkeypatch.setenv('SERVER_SOFTWARE', 'gunicorn/21.2.0')
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('FLASK_DEBUG' in e for e in errors)


def test_gunicorn_rejects_developer_mode(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('DEVELOPER_MODE', 'true')
    monkeypatch.setenv('SERVER_SOFTWARE', 'gunicorn/21.2.0')
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('DEVELOPER_MODE' in e for e in errors)


def test_invalid_postgres_port(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('POSTGRES_PORT', 'abc')
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('POSTGRES_PORT' in e for e in errors)


def test_invalid_gunicorn_workers(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('GUNICORN_WORKERS', 'many')
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('GUNICORN_WORKERS' in e for e in errors)


def test_multi_worker_oauth_requires_redis(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('GUNICORN_WORKERS', '2')
    monkeypatch.setenv('GOOGLE_OAUTH_CLIENT_ID', 'client.apps.googleusercontent.com')
    monkeypatch.delenv('REDIS_URL', raising=False)
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('REDIS_URL' in e for e in errors)


def test_multi_worker_without_oauth_does_not_require_redis(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('GUNICORN_WORKERS', '4')
    monkeypatch.delenv('GOOGLE_OAUTH_CLIENT_ID', raising=False)
    ok, errors, _ = EnvValidator.validate()
    assert ok, errors


def test_production_redis_url_must_be_reachable(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('REDIS_URL', 'redis://127.0.0.1:1/0')
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('REDIS_URL' in e for e in errors)


def test_missing_database_credentials(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('POSTGRES_USER', raising=False)
    monkeypatch.delenv('POSTGRES_PASSWORD', raising=False)
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('DATABASE_URL' in e or 'POSTGRES' in e for e in errors)


def test_n8n_secret_required_when_webhook_set(monkeypatch):
    _prod_base(monkeypatch)
    monkeypatch.setenv('N8N_WEBHOOK_URL', 'https://n8n.example/webhook')
    monkeypatch.delenv('N8N_CALLBACK_SECRET', raising=False)
    ok, errors, _ = EnvValidator.validate()
    assert not ok
    assert any('N8N_CALLBACK_SECRET' in e for e in errors)
