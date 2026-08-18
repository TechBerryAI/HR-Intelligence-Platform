"""Production-hardening HTTP/security regressions (no live Redis required)."""
from __future__ import annotations

import inspect
import sys
from io import BytesIO
from pathlib import Path

import pytest
from flask import Flask

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _try_create_app():
    try:
        from app.bootstrap.create_app import create_app

        return create_app()
    except (SystemExit, RuntimeError) as exc:
        pytest.skip(f'create_app unavailable: {exc}')


def test_client_ip_ignores_xff_by_default(monkeypatch):
    monkeypatch.delenv('TRUST_PROXY_HEADERS', raising=False)
    from app.domains.recruitment.api.parsing import _client_ip

    app = Flask(__name__)
    with app.test_request_context(
        '/',
        headers={'X-Forwarded-For': '203.0.113.9'},
        environ_base={'REMOTE_ADDR': '10.0.0.8'},
    ):
        assert _client_ip() == '10.0.0.8'


def test_client_ip_uses_xff_when_trusted(monkeypatch):
    monkeypatch.setenv('TRUST_PROXY_HEADERS', 'true')
    from app.domains.recruitment.api.parsing import _client_ip

    app = Flask(__name__)
    with app.test_request_context(
        '/',
        headers={'X-Forwarded-For': '203.0.113.9'},
        environ_base={'REMOTE_ADDR': '10.0.0.8'},
    ):
        assert _client_ip() == '203.0.113.9'


def test_parse_progress_omits_result():
    from app.ai.parser.engine.progress import (
        complete_parse_job,
        create_parse_job,
        reset_parse_jobs_for_tests,
    )
    from app.domains.recruitment.api.parsing import parsing_bp

    reset_parse_jobs_for_tests()
    app = Flask(__name__)
    app.register_blueprint(parsing_bp, url_prefix='/api')
    job_id = create_parse_job('resume')
    complete_parse_job(job_id, {'toon': {'person': {'email': 'secret@x.test'}}, 'status': 'ok'})
    res = app.test_client().get(f'/api/parse/jobs/{job_id}/progress')
    assert res.status_code == 200
    body = res.get_json()
    assert 'result' not in body
    assert 'toon' not in body
    assert 'secret@x.test' not in res.get_data(as_text=True)
    assert body.get('job_status') == 'completed'
    reset_parse_jobs_for_tests()


def test_public_parse_generic_500(monkeypatch, caplog):
    from app.domains.recruitment.api import parsing as parsing_mod

    secret_exc = (
        'postgresql://user:DB_PASSWORD_SECRET@host/db '
        'Bearer TOP_SECRET_TOKEN_ABC '
        'https://service.example/webhook/WEBHOOK_SECRET_123'
    )

    def boom(*_a, **_k):
        raise RuntimeError(secret_exc)

    monkeypatch.setattr(parsing_mod, 'run_resume_parse_pipeline', boom)
    monkeypatch.setattr(parsing_mod, '_public_parse_rate_limited', lambda *_a, **_k: False)
    caplog.set_level(__import__('logging').ERROR)
    app = Flask(__name__)
    app.register_blueprint(parsing_mod.parsing_bp, url_prefix='/api')
    data = {'file': (BytesIO(b'%PDF-fake'), 'cv.pdf')}
    res = app.test_client().post('/api/parse/resume/public', data=data)
    assert res.status_code == 500
    body = res.get_json()
    err = str(body.get('error') or '')
    assert err == 'Internal server error'
    blob = res.get_data(as_text=True) + caplog.text
    assert 'super-secret' not in blob
    assert 'DB_PASSWORD_SECRET' not in blob
    assert 'TOP_SECRET_TOKEN_ABC' not in blob
    assert 'WEBHOOK_SECRET_123' not in blob


def test_pipeline_error_body_not_forwarded(monkeypatch):
    from app.domains.recruitment.api import parsing as parsing_mod

    monkeypatch.setattr(
        parsing_mod,
        'run_resume_parse_pipeline',
        lambda *_a, **_k: (
            {'status': 'error', 'error': 'postgresql://user:DB_PASSWORD_SECRET@host/db'},
            500,
        ),
    )
    monkeypatch.setattr(parsing_mod, '_public_parse_rate_limited', lambda *_a, **_k: False)
    app = Flask(__name__)
    app.register_blueprint(parsing_mod.parsing_bp, url_prefix='/api')
    res = app.test_client().post(
        '/api/parse/resume/public',
        data={'file': (BytesIO(b'%PDF-fake'), 'cv.pdf')},
    )
    assert res.status_code == 500
    text = res.get_data(as_text=True)
    assert 'Internal server error' in text
    assert 'DB_PASSWORD_SECRET' not in text


def test_reject_public_oversize_content_length():
    from app.domains.recruitment.api.parsing import MAX_FILE_SIZE, _reject_public_oversize

    app = Flask(__name__)
    with app.test_request_context('/', method='POST', content_length=MAX_FILE_SIZE + 1):
        resp = _reject_public_oversize()
        assert resp is not None
        _json, code = resp
        assert code == 413


def test_public_parse_413_after_read(monkeypatch):
    from app.domains.recruitment.api import parsing as parsing_mod

    monkeypatch.setattr(parsing_mod, '_reject_public_oversize', lambda: None)
    monkeypatch.setattr(parsing_mod, '_public_parse_rate_limited', lambda *_a, **_k: False)
    app = Flask(__name__)
    app.register_blueprint(parsing_mod.parsing_bp, url_prefix='/api')
    oversized = b'x' * (parsing_mod.MAX_FILE_SIZE + 1)
    res = app.test_client().post(
        '/api/parse/resume/public',
        data={'file': (BytesIO(oversized), 'cv.pdf')},
    )
    assert res.status_code == 413


def test_otp_rate_limited(monkeypatch):
    monkeypatch.setattr(
        'app.domains.identity.api.hr_auth.shared_store.rate_limit_hit',
        lambda *_a, **_k: True,
    )
    from app.domains.identity.api.hr_auth import _otp_rate_limited

    app = Flask(__name__)
    with app.test_request_context('/', environ_base={'REMOTE_ADDR': '203.0.113.1'}):
        assert _otp_rate_limited('user@example.com') is True


def test_verify_otp_returns_429(monkeypatch):
    monkeypatch.setattr(
        'app.domains.identity.api.hr_auth._otp_rate_limited',
        lambda *_a, **_k: True,
    )
    from app.domains.identity.api.hr_auth import auth_bp

    app = Flask(__name__)
    app.register_blueprint(auth_bp, url_prefix='/api')
    res = app.test_client().post(
        '/api/verify-otp',
        json={'email': 'user@example.com', 'otp': '123456'},
    )
    assert res.status_code == 429
    assert 'Too many OTP' in (res.get_json() or {}).get('error', '')


def test_resend_otp_returns_429(monkeypatch):
    monkeypatch.setattr(
        'app.domains.identity.api.hr_auth._otp_rate_limited',
        lambda *_a, **_k: True,
    )
    from app.domains.identity.api.hr_auth import auth_bp

    app = Flask(__name__)
    app.register_blueprint(auth_bp, url_prefix='/api')
    res = app.test_client().post(
        '/api/resend-otp',
        json={'email': 'user@example.com'},
    )
    assert res.status_code == 429


def test_inprocess_join_uses_timeout():
    from app.ai.parser.engine.parse_inflight import run_or_join

    src = inspect.getsource(run_or_join)
    assert 'fut.result(timeout=join_timeout_sec())' in src


def test_ready_includes_redis_when_configured(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'true')
    monkeypatch.setenv('REDIS_URL', 'redis://127.0.0.1:1/0')
    monkeypatch.setenv('GUNICORN_WORKERS', '1')
    monkeypatch.setattr('app.core.shared_store.redis_status', lambda: 'error')
    app = _try_create_app()
    res = app.test_client().get('/ready')
    body = res.get_json() or {}
    assert 'redis' in body
    if body.get('postgres') == 'ok':
        assert res.status_code == 503
        assert body.get('redis') == 'error'


def test_test_cors_only_when_debug(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'true')
    app = _try_create_app()
    res = app.test_client().get('/api/test-cors')
    assert res.status_code == 200
    assert 'allowed_origins' in (res.get_json() or {})


def test_test_cors_404_when_not_debug(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('GUNICORN_WORKERS', '1')
    monkeypatch.setattr(
        'app.bootstrap.create_app.EnvValidator.validate',
        lambda: (True, [], []),
    )
    app = _try_create_app()
    res = app.test_client().get('/api/test-cors')
    assert res.status_code == 404
