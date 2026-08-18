"""Canonical Redis URL handling. Never log the password."""
from __future__ import annotations

from urllib.parse import unquote, quote

_REDIS_SCHEMES = ('rediss://', 'redis://')


def canonicalize_redis_url(url: str) -> str:
    """Return a redis-py-safe URL with userinfo percent-encoded.

    Passwords containing ``/`` or ``=`` are split incorrectly by urllib unless
    encoded. Splits on the last ``@`` so an unencoded ``/`` in the password
    still yields the real host. Already-encoded URLs are not double-encoded.
    """
    raw = (url or '').strip()
    if not raw:
        return raw
    lower = raw.lower()
    scheme = None
    rest = raw
    for prefix in _REDIS_SCHEMES:
        if lower.startswith(prefix):
            scheme = prefix[:-3]  # redis / rediss
            rest = raw[len(prefix):]
            break
    if scheme is None or '@' not in rest:
        return raw
    userinfo, hostpart = rest.rsplit('@', 1)
    if not hostpart:
        return raw
    if ':' in userinfo:
        user, password = userinfo.split(':', 1)
    else:
        user, password = '', userinfo
    encoded_user = quote(unquote(user), safe='') if user else ''
    encoded_password = quote(unquote(password), safe='')
    auth = f'{encoded_user}:{encoded_password}'
    return f'{scheme}://{auth}@{hostpart}'


def redis_endpoint_for_log(url: str) -> str:
    """Host/port/db only. Empty if the URL has no ``@`` authority split."""
    raw = (url or '').strip()
    if not raw:
        return '(not configured)'
    if '@' in raw:
        return raw.rsplit('@', 1)[-1]
    lower = raw.lower()
    for prefix in _REDIS_SCHEMES:
        if lower.startswith(prefix):
            return raw[len(prefix):]
    return '(configured)'


def safe_redis_error(exc: BaseException) -> str:
    """Exception summary with Redis URLs and userinfo stripped."""
    from app.core.log_redaction import redact_text

    msg = redact_text(str(exc) or type(exc).__name__)
    return f'{type(exc).__name__}: {msg}'[:400]
