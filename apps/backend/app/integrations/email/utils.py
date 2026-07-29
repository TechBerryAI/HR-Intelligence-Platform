from typing import Optional

from flask import current_app
from flask_mail import Message

from app.bootstrap.extensions import mail
from app.integrations.email.mail_send import send_with_timeout_and_retries


def send_notification_email(
    recipient: Optional[str],
    subject: str,
    body: str,
    html: Optional[str] = None,
) -> bool:
    """
    Send a notification email. Uses plain text body; if html is provided,
    sends multipart (plain + HTML) so clients show the HTML version.
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
        if html:
            msg.html = html
        if not send_with_timeout_and_retries(msg):
            if current_app:
                current_app.logger.error("Notification email send failed after retries (to=%s)", recipient)
            else:
                print(f"Failed to send notification email to {recipient}")
            return False
        return True
    except Exception as exc:
        if current_app:
            current_app.logger.error("Failed to send notification email: %s", exc, exc_info=True)
        else:
            print(f"Failed to send notification email: {exc}")
        return False

