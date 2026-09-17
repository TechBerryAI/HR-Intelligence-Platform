"""Ollama startup probe — tags/list only, no generation."""
from __future__ import annotations

from app.ai.parser.engine.ollama_health import inspect_ollama_runtime, log_ollama_runtime


def test_inspect_not_configured(monkeypatch):
    monkeypatch.delenv('OLLAMA_HOST', raising=False)
    monkeypatch.delenv('OLLAMA_BASE_URL', raising=False)
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5:14b-instruct')
    info = inspect_ollama_runtime()
    assert info['error'] == 'not_configured'
    assert info['reachable'] is False
    assert info['model_available'] is False
    assert info['model'] == 'qwen2.5:14b-instruct'


def test_inspect_model_available(monkeypatch):
    monkeypatch.setenv('OLLAMA_HOST', 'http://127.0.0.1:11434')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5:14b-instruct')

    class _Resp:
        ok = True
        status_code = 200

        def json(self):
            return {
                'models': [
                    {'name': 'qwen2.5:7b-instruct'},
                    {'name': 'qwen2.5:14b-instruct'},
                ]
            }

    monkeypatch.setattr('requests.get', lambda *a, **k: _Resp())
    info = inspect_ollama_runtime()
    assert info['host'] == 'http://127.0.0.1:11434'
    assert info['reachable'] is True
    assert info['model_available'] is True


def test_inspect_reachable_but_model_missing(monkeypatch, capsys):
    monkeypatch.setenv('OLLAMA_HOST', 'http://192.168.1.200:11434')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5:14b-instruct')

    class _Resp:
        ok = True
        status_code = 200

        def json(self):
            return {'models': []}

    monkeypatch.setattr('requests.get', lambda *a, **k: _Resp())
    info = inspect_ollama_runtime()
    assert info['reachable'] is True
    assert info['model_available'] is False
    log_ollama_runtime()
    err = capsys.readouterr()
    combined = err.out + err.err
    assert 'qwen2.5:14b-instruct is unavailable on this host' in combined
    assert 'semantic_single_llm_fix=enabled' in combined
    assert 'reachable=true' in combined
    assert 'model_available=false' in combined


# --- Host normalization -----------------------------------------------------
#
# OLLAMA_HOST is Ollama's own server bind setting, so a machine running an
# Ollama server typically exports OLLAMA_HOST=0.0.0.0:11434 user-wide. That
# shadows this app's .env (dotenv does not override real env vars) and is
# schemeless, which made requests raise InvalidSchema — /health then reported a
# perfectly healthy Ollama as unreachable.

import pytest

from app.ai.parser.engine.ollama_health import normalize_ollama_url


@pytest.mark.parametrize(
    'raw,expected',
    [
        ('0.0.0.0:11434', 'http://127.0.0.1:11434'),
        ('http://0.0.0.0:11434', 'http://127.0.0.1:11434'),
        ('192.168.1.200:11434', 'http://192.168.1.200:11434'),
        ('http://192.168.1.200:11434', 'http://192.168.1.200:11434'),
        ('http://127.0.0.1:11434/', 'http://127.0.0.1:11434'),
        ('  http://host:11434  ', 'http://host:11434'),
        ('https://ollama.internal', 'https://ollama.internal'),
        ('', ''),
    ],
)
def test_normalize_ollama_url(raw, expected):
    assert normalize_ollama_url(raw) == expected


def test_legacy_base_url_is_used_only_when_host_is_unset(monkeypatch):
    """OLLAMA_HOST stays primary; OLLAMA_BASE_URL remains the legacy fallback."""
    monkeypatch.delenv('OLLAMA_HOST', raising=False)
    monkeypatch.setenv('OLLAMA_BASE_URL', '192.168.1.200:11434')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5:14b-instruct')

    seen = {}

    class _Resp:
        ok = True
        status_code = 200

        def json(self):
            return {'models': [{'name': 'qwen2.5:14b-instruct'}]}

    import requests

    monkeypatch.setattr(
        requests, 'get', lambda url, timeout=None: (seen.update(url=url), _Resp())[1]
    )
    info = inspect_ollama_runtime()

    assert info['host'] == 'http://192.168.1.200:11434'
    assert seen['url'] == 'http://192.168.1.200:11434/api/tags'
    assert info['reachable'] is True


def test_schemeless_host_no_longer_fails(monkeypatch):
    """The exact failure seen in the field: schemeless host -> InvalidSchema."""
    monkeypatch.delenv('OLLAMA_BASE_URL', raising=False)
    monkeypatch.setenv('OLLAMA_HOST', '0.0.0.0:11434')
    monkeypatch.setenv('OLLAMA_MODEL', 'qwen2.5:14b-instruct')

    class _Resp:
        ok = True
        status_code = 200

        def json(self):
            return {'models': [{'name': 'qwen2.5:14b-instruct'}]}

    import requests

    monkeypatch.setattr(requests, 'get', lambda url, timeout=None: _Resp())
    info = inspect_ollama_runtime()

    assert info['error'] is None
    assert info['reachable'] is True
