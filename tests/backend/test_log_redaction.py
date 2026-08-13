"""Regression: sensitive credentials must never appear in request logging helpers."""
from __future__ import annotations

import io
from contextlib import redirect_stdout

from app.core.log_redaction import (
    REDACTED,
    redact_headers,
    redact_mapping,
    safe_header_repr,
)


def test_redact_headers_strips_authorization_and_cookies():
    headers = {
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret',
        'Cookie': 'session=abc; refresh_token=xyz',
        'Set-Cookie': 'session=abc; HttpOnly',
        'X-API-Key': 'sk-live-123',
        'Proxy-Authorization': 'Basic dXNlcjpwYXNz',
        'Content-Type': 'application/json',
        'Host': 'example.test',
    }
    safe = redact_headers(headers)
    assert safe['Authorization'] == REDACTED
    assert safe['Cookie'] == REDACTED
    assert safe['Set-Cookie'] == REDACTED
    assert safe['X-API-Key'] == REDACTED
    assert safe['Proxy-Authorization'] == REDACTED
    assert safe['Content-Type'] == 'application/json'
    assert safe['Host'] == 'example.test'
    # Original must be unchanged
    assert headers['Authorization'].startswith('Bearer ')


def test_safe_header_repr_never_emits_bearer_token():
    token = 'Bearer FAKESECRET_g1h2i3j4k5l6m7n8o9p0'
    text = safe_header_repr({'Authorization': token, 'Accept': 'application/json'})
    assert 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' not in text
    assert 'Bearer FAKE' not in text
    assert REDACTED in text
    assert 'Accept' in text


def test_redact_mapping_scrubs_oauth_fields():
    payload = {
        'scope': 'calendar',
        'token_type': 'Bearer',
        'access_token': 'ya29.secret',
        'refresh_token': '1//secret',
        'id_token': 'eyJ.secret',
        'client_secret': 'goog-secret',
        'nested': {'password': 'p@ss', 'email': 'a@b.com'},
    }
    safe = redact_mapping(payload)
    assert safe['scope'] == 'calendar'
    assert safe['access_token'] == REDACTED
    assert safe['refresh_token'] == REDACTED
    assert safe['id_token'] == REDACTED
    assert safe['client_secret'] == REDACTED
    assert safe['nested']['password'] == REDACTED
    assert safe['nested']['email'] == 'a@b.com'


def test_create_job_does_not_print_authorization(monkeypatch):
    """Ensure create_job no longer dumps request headers to stdout."""
    from app.domains.recruitment.api import jobs as jobs_mod

    # Source-level guard: the dangerous pattern must not exist.
    import inspect

    src = inspect.getsource(jobs_mod.create_job)
    assert 'dict(request.headers)' not in src
    assert 'Headers:' not in src


def test_print_of_raw_headers_would_be_caught_by_redaction():
    """Simulate the old bug path: printing headers must go through redaction."""
    headers = {
        'Authorization': 'Bearer leak-me-now',
        'Cookie': 'refresh_token=leak-cookie',
    }
    buf = io.StringIO()
    with redirect_stdout(buf):
        print(f'Headers: {safe_header_repr(headers)}')
    out = buf.getvalue()
    assert 'leak-me-now' not in out
    assert 'leak-cookie' not in out
    assert REDACTED in out
