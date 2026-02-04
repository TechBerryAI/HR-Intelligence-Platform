"""
Send email with timeout and retries. Flask-Mail has no built-in timeout;
blocking send can hang the request. This module runs mail.send() in a
thread with a configurable timeout and retries on failure.
"""
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from flask import current_app

from extensions import mail


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
            if current_app:
                current_app.logger.warning(
                    "Mail send timeout (attempt %s/%s, timeout=%ss)",
                    attempt + 1, retries, timeout,
                )
            else:
                print(f"[MAIL] Timeout (attempt {attempt + 1}/{retries})")
        except Exception as e:
            last_exc = e
            if current_app:
                current_app.logger.warning(
                    "Mail send failed: %s\n%s",
                    e, traceback.format_exc(),
                )
            else:
                print(f"[MAIL] Send failed: {e}\n{traceback.format_exc()}")
        if attempt < retries - 1:
            time.sleep(1 + attempt)
    err_msg = f"Mail send failed after {retries} attempts: {last_exc}"
    if current_app:
        current_app.logger.error(err_msg)
    print(f"[MAIL] {err_msg}")
    if last_exc and hasattr(last_exc, "__traceback__") and last_exc.__traceback__:
        import traceback
        traceback.print_exception(type(last_exc), last_exc, last_exc.__traceback__)
    return False
