"""
Send email with timeout and retries. Flask-Mail has no built-in timeout;
blocking send can hang the request. This module runs mail.send() in a
thread with a configurable timeout and retries on failure.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from flask import current_app

from app.bootstrap.extensions import mail
from app.core.errors import log_unexpected

logger = logging.getLogger(__name__)


def send_with_timeout_and_retries(msg) -> bool:
    """
    Send a flask_mail Message with MAIL_TIMEOUT and MAIL_SEND_RETRIES.
    Must be called from an active Flask app context.
    """
    app = current_app._get_current_object()
    timeout = app.config.get("MAIL_TIMEOUT", 25)
    retries = max(1, app.config.get("MAIL_SEND_RETRIES", 3))
    last_exc = None

    def _send():
        with app.app_context():
            mail.send(msg)

    for attempt in range(retries):
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_send)
                future.result(timeout=timeout)
            return True
        except FuturesTimeoutError as e:
            last_exc = e
            logger.warning(
                "Mail send timeout (attempt %s/%s, timeout=%ss)",
                attempt + 1, retries, timeout,
            )
        except Exception as e:
            last_exc = e
            log_unexpected('mail_send', e, attempt=attempt + 1, retries=retries)
        if attempt < retries - 1:
            time.sleep(1 + attempt)
    log_unexpected('mail_send_exhausted', last_exc or RuntimeError('mail send failed'), retries=retries)
    return False
