from typing import Optional

from flask import current_app
from flask_mail import Message

from extensions import mail


def send_notification_email(recipient: Optional[str], subject: str, body: str) -> bool:
    """
    Send a generic notification email (signup confirmation, password change, login alert, etc.).
    Returns True when the email was queued/simulated successfully.
    """
    if not recipient:
        return False
    try:
        cfg = current_app.config if current_app else {}
        suppress_send = cfg.get('MAIL_SUPPRESS_SEND')
        missing_creds = not cfg.get('MAIL_USERNAME') or not cfg.get('MAIL_PASSWORD')
        if suppress_send or missing_creds:
            message = f"[DEV EMAIL] To: {recipient}\nSubject: {subject}\n\n{body}"
            if current_app:
                current_app.logger.info(message)
            else:
                print(message)
            return True

        msg = Message(subject=subject, recipients=[recipient], body=body)
        mail.send(msg)
        return True
    except Exception as exc:
        if current_app:
            current_app.logger.error("Failed to send notification email: %s", exc)
        else:
            print(f"Failed to send notification email: {exc}")
        return False

