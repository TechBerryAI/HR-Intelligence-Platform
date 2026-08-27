"""Startup /health Ollama probes — tags only, no generation, no resume text."""
from __future__ import annotations

import os
import sys
from typing import Any

SEMANTIC_SINGLE_LLM_FIX = 'enabled'


def inspect_ollama_runtime(*, timeout_sec: float = 2.0) -> dict[str, Any]:
    """Return host/model reachability from the process environment.

    Does not send a chat/generate request. Used at Flask startup and /health.
    """
    host = (os.getenv('OLLAMA_HOST') or os.getenv('OLLAMA_BASE_URL') or '').strip().rstrip(
        '/'
    )
    model = (os.getenv('OLLAMA_MODEL') or '').strip()
    reachable = False
    model_available = False
    error: str | None = None
    if not host:
        return {
            'host': '',
            'model': model,
            'reachable': False,
            'model_available': False,
            'error': 'not_configured',
        }
    try:
        import requests

        response = requests.get(f'{host}/api/tags', timeout=timeout_sec)
        if not response.ok:
            return {
                'host': host,
                'model': model,
                'reachable': False,
                'model_available': False,
                'error': f'http_{response.status_code}',
            }
        reachable = True
        wanted = model.lower()
        for item in (response.json() or {}).get('models') or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get('name') or item.get('model') or '').lower().strip()
            if not wanted or not name:
                continue
            if name == wanted:
                model_available = True
                break
            if ':' not in wanted and name == f'{wanted}:latest':
                model_available = True
                break
    except Exception as exc:
        error = type(exc).__name__
    return {
        'host': host,
        'model': model,
        'reachable': reachable,
        'model_available': model_available,
        'error': error,
    }


def log_ollama_runtime() -> dict[str, Any]:
    """Print operator-facing Ollama status (no PII, no resume text)."""
    info = inspect_ollama_runtime()
    host = info.get('host') or '(unset)'
    model = info.get('model') or '(unset)'
    print(f'[ollama] host={host}')
    print(f'[ollama] model={model}')
    print(f"[ollama] reachable={str(bool(info.get('reachable'))).lower()}")
    print(f"[ollama] model_available={str(bool(info.get('model_available'))).lower()}")
    print(f'[backend] semantic_single_llm_fix={SEMANTIC_SINGLE_LLM_FIX}')
    if info.get('host') and info.get('reachable') and info.get('model') and not info.get(
        'model_available'
    ):
        msg = (
            f'Ollama is reachable but configured model {model} is unavailable on this host.'
        )
        print(msg, file=sys.stderr)
        print(f'[ollama] ERROR {msg}')
    return info
