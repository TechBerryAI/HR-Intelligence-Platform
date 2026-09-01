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
