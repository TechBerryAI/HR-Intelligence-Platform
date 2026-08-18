"""Safe logging helpers — redact credentials from headers, text, and log records."""
from __future__ import annotations

import logging
import re
from typing import Any, Mapping

# Header names compared case-insensitively.
SENSITIVE_HEADERS = frozenset(
    {
        'authorization',
        'proxy-authorization',
        'cookie',
        'set-cookie',
        'x-api-key',
        'x-platform-key',
        'x-n8n-callback-secret',
        'x-validation-token',
    }
)

# Dict/JSON keys that must never appear in plaintext logs.
SENSITIVE_FIELD_NAMES = frozenset(
    {
        'access_token',
        'refresh_token',
        'id_token',
        'client_secret',
        'authorization',
        'password',
        'passwd',
        'secret',
        'token',
        'api_key',
        'apikey',
        'raw_json',
    }
)

REDACTED = '[REDACTED]'

_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'(?i)\bbearer\s+\S+'), f'Bearer {REDACTED}'),
    (re.compile(r'(?i)\bbasic\s+\S+'), f'Basic {REDACTED}'),
    (re.compile(r'(?i)(authorization:\s*)[^\r\n]+'), rf'\1{REDACTED}'),
    (re.compile(r'(?i)(cookie:\s*)[^\r\n]+'), rf'\1{REDACTED}'),
    (re.compile(r'(?i)(session=)[^\s;]+'), rf'\1{REDACTED}'),
    (
        re.compile(r'(?i)(postgres(?:ql)?(?:\+\w+)?://[^:\s/]+:)[^@\s]+(@)'),
        rf'\1{REDACTED}\2',
    ),
    (re.compile(r'(?i)(redis://:)[^@\s]+(@)'), rf'\1{REDACTED}\2'),
    (re.compile(r'(?i)(https?://[^\s\"\']*?/webhook/)[^\s\"\'/?#]+'), rf'\1{REDACTED}'),
)

_installed = False
_orig_format_exception = logging.Formatter.formatException
_orig_record_factory = logging.getLogRecordFactory()


def _is_sensitive_header(name: str) -> bool:
    return (name or '').strip().lower() in SENSITIVE_HEADERS


def _is_sensitive_field(name: str) -> bool:
    key = (name or '').strip().lower()
    if key in SENSITIVE_FIELD_NAMES:
        return True
    if key.endswith('_token') or key.endswith('_secret') or key.endswith('_password'):
        return True
    return False


def redact_text(value: Any) -> str:
    """Redact credential-shaped substrings from a log/error string."""
    text = '' if value is None else str(value)
    for pattern, repl in _TEXT_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def redact_headers(headers: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a copy of request/response headers with credentials redacted."""
    if not headers:
        return {}
    out: dict[str, Any] = {}
    for key, value in headers.items():
        out[str(key)] = REDACTED if _is_sensitive_header(str(key)) else value
    return out


def safe_header_repr(headers: Mapping[str, Any] | None) -> str:
    """String form safe for print/logging."""
    return repr(redact_headers(headers))


def redact_mapping(data: Mapping[str, Any] | None, *, depth: int = 0) -> dict[str, Any]:
    """Redact sensitive keys in a shallow/nested mapping (max depth 4)."""
    if not data or depth > 4:
        return {}
    out: dict[str, Any] = {}
    for key, value in data.items():
        k = str(key)
        if _is_sensitive_field(k) or _is_sensitive_header(k):
            out[k] = REDACTED
        elif isinstance(value, Mapping):
            out[k] = redact_mapping(value, depth=depth + 1)
        elif isinstance(value, str):
            out[k] = redact_text(value)
        else:
            out[k] = value
    return out


class SensitiveDataFilter(logging.Filter):
    """Last-line filter so a logger cannot bypass redaction via a custom handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(record.getMessage())
            record.args = ()
        except Exception:
            pass
        if record.exc_text:
            record.exc_text = redact_text(record.exc_text)
        return True


def _redacting_format_exception(self, ei) -> str:
    return redact_text(_orig_format_exception(self, ei))


def _redacting_record_factory(*args, **kwargs) -> logging.LogRecord:
    record = _orig_record_factory(*args, **kwargs)
    orig_get = record.getMessage

    def getMessage() -> str:
        return redact_text(orig_get())

    record.getMessage = getMessage  # type: ignore[method-assign]
    return record


def install_log_redaction() -> None:
    """Install process-wide redaction so Flask/Gunicorn/root/third-party loggers share it."""
    global _installed
    if _installed:
        return
    logging.setLogRecordFactory(_redacting_record_factory)
    logging.Formatter.formatException = _redacting_format_exception  # type: ignore[method-assign]
    filt = SensitiveDataFilter()
    root = logging.getLogger()
    if not any(isinstance(f, SensitiveDataFilter) for f in root.filters):
        root.addFilter(filt)
    for handler in list(root.handlers):
        if not any(isinstance(f, SensitiveDataFilter) for f in handler.filters):
            handler.addFilter(filt)
    for name in (
        'flask',
        'flask.app',
        'gunicorn',
        'gunicorn.error',
        'gunicorn.access',
        'hcip.request',
        'werkzeug',
    ):
        log = logging.getLogger(name)
        if not any(isinstance(f, SensitiveDataFilter) for f in log.filters):
            log.addFilter(filt)
        for handler in list(log.handlers):
            if not any(isinstance(f, SensitiveDataFilter) for f in handler.filters):
                handler.addFilter(filt)
    _installed = True
