"""Safe unexpected-error logging and client responses."""
from __future__ import annotations

import logging
from typing import Any

from flask import has_request_context, jsonify, request

SAFE_INTERNAL_ERROR = 'Internal server error'

logger = logging.getLogger('hcip.errors')


def _request_id() -> str | None:
    if not has_request_context():
        return None
    rid = getattr(request, 'timing_request_id', None)
    if rid:
        return str(rid)
    return request.headers.get('X-Request-ID') or request.headers.get('X-Correlation-ID')


def log_unexpected(operation: str, exc: BaseException, **extra: Any) -> None:
    """Log an unexpected exception with operation metadata (message is redacted globally)."""
    payload = {k: v for k, v in extra.items() if v is not None}
    rid = _request_id()
    logger.exception(
        'operation=%s error_type=%s request_id=%s extra=%s',
        operation,
        type(exc).__name__,
        rid or '-',
        payload or '-',
    )


def client_internal_error():
    return jsonify({'error': SAFE_INTERNAL_ERROR}), 500
