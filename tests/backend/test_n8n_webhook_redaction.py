"""N8N webhook URL/token must not leak to clients or logs."""
from __future__ import annotations

import logging

import requests

SECRET_URL = 'https://n8n.example/webhook/SUPER_SECRET_TOKEN_123'


def test_trigger_n8n_hides_secret_url(monkeypatch, caplog):
    from app.domains.recruitment.api import applications as apps_mod

    monkeypatch.setattr(apps_mod, 'N8N_WEBHOOK_URL', SECRET_URL)

    def boom(url, **_kwargs):
        raise requests.exceptions.HTTPError(f'404 Client Error for url: {url}')

    monkeypatch.setattr(apps_mod.requests, 'post', boom)
    caplog.set_level(logging.DEBUG)
    result = apps_mod.trigger_n8n('cand-1', 'job-1', {'toon': {}}, {'toon': {}})
    blob = caplog.text + str(result)
    assert result.get('success') is False
    assert result.get('error') == 'External workflow request failed'
    assert 'SUPER_SECRET_TOKEN_123' not in blob
    assert SECRET_URL not in blob
