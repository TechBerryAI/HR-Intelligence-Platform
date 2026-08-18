"""Optional JSON-ish request logging when LOG_FORMAT=json."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from flask import Flask, g, request


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log record (plus request fields when present)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            'ts': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
        }
        for key in ('method', 'path', 'status', 'duration_ms', 'request_id'):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        elif record.exc_text:
            payload['exc_info'] = record.exc_text
        return json.dumps(payload, default=str)


def configure_structured_logging(app: Flask) -> None:
    """Attach request logging. Use LOG_FORMAT=json for machine-readable lines."""
    fmt = (os.getenv('LOG_FORMAT') or '').strip().lower()
    use_json = fmt in ('json', 'jsonish', 'structured')

    logger = logging.getLogger('hcip.request')
    if not logger.handlers:
        handler = logging.StreamHandler()
        if use_json:
            handler.setFormatter(JsonLogFormatter())
        else:
            handler.setFormatter(
                logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
            )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    @app.before_request
    def _structured_log_begin():
        g._hcip_req_started = time.perf_counter()

    @app.after_request
    def _structured_log_end(response):
        started = getattr(g, '_hcip_req_started', None)
        duration_ms = None
        if started is not None:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        path = request.path or ''
        if path in ('/health', '/ready') and (response.status_code or 0) < 400:
            return response
        extra = {
            'method': request.method,
            'path': path,
            'status': response.status_code,
            'duration_ms': duration_ms,
        }
        if use_json:
            logger.info(
                'request',
                extra=extra,
            )
        else:
            logger.info(
                '%s %s %s %.2fms',
                request.method,
                path,
                response.status_code,
                duration_ms if duration_ms is not None else -1.0,
            )
        return response
