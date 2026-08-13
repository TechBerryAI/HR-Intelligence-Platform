"""Safe logging helpers — redact credentials from headers and structured fields."""
from __future__ import annotations

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


def _is_sensitive_header(name: str) -> bool:
    return (name or '').strip().lower() in SENSITIVE_HEADERS


def _is_sensitive_field(name: str) -> bool:
    key = (name or '').strip().lower()
    if key in SENSITIVE_FIELD_NAMES:
        return True
    # Catch variants: oauth_access_token, bearer_token, etc.
    if key.endswith('_token') or key.endswith('_secret') or key.endswith('_password'):
        return True
    return False


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
        else:
            out[k] = value
    return out
