import random
import re
from datetime import datetime, timezone
from typing import Optional


def utc_now_aware() -> datetime:
    """Return current UTC time as timezone-aware (for comparing with PG timestamptz)."""
    return datetime.now(timezone.utc)


def normalize_to_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert a datetime to timezone-aware UTC. Handles naive (from MSSQL) and aware (from PostgreSQL)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

from flask import current_app
from flask_mail import Message

from extensions import mail
from helpers.mail_send import send_with_timeout_and_retries

GMAIL_REGEX = re.compile(r'^[A-Za-z0-9._%+-]+@gmail\.com$', re.IGNORECASE)
# General email regex: accepts any email with @ symbol and valid domain
EMAIL_REGEX = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$', re.IGNORECASE)
INDIAN_PHONE_REGEX = re.compile(r'^[6-9]\d{9}$')


def generate_otp() -> str:
    return f"{random.randint(100000, 999999):06d}"


def is_valid_email(email: Optional[str]) -> bool:
    """
    Validate any email address (institute, corporate, or personal).
    Checks for @ symbol and valid email format.
    """
    if not email:
        return False
    email = email.strip()
    # Basic check: must contain @ symbol
    if '@' not in email:
        return False
    # Validate email format using regex
    return bool(EMAIL_REGEX.match(email))


def is_valid_gmail(email: Optional[str]) -> bool:
    """Legacy function - kept for backward compatibility"""
    if not email:
        return False
    return bool(GMAIL_REGEX.match(email.strip()))


def is_valid_indian_phone(phone: Optional[str]) -> bool:
    if not phone:
        return False
    digits_only = re.sub(r'\D', '', phone)
    return bool(INDIAN_PHONE_REGEX.match(digits_only))


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits_only = re.sub(r'\D', '', phone)
    if digits_only.startswith('91') and len(digits_only) == 12:
        digits_only = digits_only[2:]
    if digits_only.startswith('0') and len(digits_only) == 11:
        digits_only = digits_only[1:]
    return digits_only if digits_only else None


def send_email_otp(recipient: str, otp: str, user_type: str = "Candidate") -> bool:
    if not recipient:
        return False
    try:
        print(f"[SEND_EMAIL_OTP] Called with recipient={recipient}, otp={otp}, user_type={user_type}")
        cfg = current_app.config if current_app else {}
        suppress_send = cfg.get('MAIL_SUPPRESS_SEND')
        missing_creds = not cfg.get('MAIL_USERNAME') or not cfg.get('MAIL_PASSWORD')
        if suppress_send or missing_creds:
            if current_app:
                current_app.logger.info("Dev email OTP (not sent) to %s: %s", recipient, otp)
            else:
                print(f"[SEND_EMAIL_OTP] Dev mode - OTP for {recipient}: {otp}")
            return True
        subject = "Your Job Portal OTP"
        greeting = "Dear HR," if user_type.lower() == "hr" else "Dear Candidate,"
        body = (
            f"{greeting}\n\n"
            f"Your One-Time Password (OTP) is: {otp}\n"
            f"This code is valid for 5 minutes.\n\n"
            f"If you did not request this OTP, please ignore this email.\n\n"
            f"Regards,\nJob Portal Team"
        )
        print(f"[SEND_EMAIL_OTP] Sending email to {recipient} with OTP: {otp}")
        msg = Message(subject=subject, recipients=[recipient], body=body)
        ok = send_with_timeout_and_retries(msg)
        if ok:
            print(f"[SEND_EMAIL_OTP] Email sent successfully to {recipient}")
        return ok
    except Exception as exc:
        if current_app:
            current_app.logger.error("Failed to send email OTP: %s", exc, exc_info=True)
        else:
            print(f"[SEND_EMAIL_OTP] Failed to send email OTP: {exc}")
        return False


def send_sms_otp(phone: str, otp: str) -> bool:
    if not phone:
        return False
    try:
        if current_app:
            current_app.logger.info("Simulating Fast2SMS OTP send to %s: %s", phone, otp)
        else:
            print(f"Simulating Fast2SMS OTP send to {phone}: {otp}")
        return True
    except Exception as exc:
        if current_app:
            current_app.logger.error("Failed to send SMS OTP: %s", exc)
        else:
            print(f"Failed to send SMS OTP: {exc}")
        return False


def parse_otp_expiry(raw_expiry) -> Optional[datetime]:
    """
    Normalize OTP expiry values coming from SQLAlchemy/pyodbc into datetime.
    """
    if not raw_expiry:
        return None
    if isinstance(raw_expiry, datetime):
        return raw_expiry
    if isinstance(raw_expiry, str):
        candidate = raw_expiry.strip().replace('Z', '')
        candidate = candidate.replace('T', ' ')
        if '.' in candidate:
            candidate = candidate.split('.')[0]
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            try:
                from dateutil import parser  # type: ignore
                return parser.parse(raw_expiry)
            except Exception:
                return None
    if hasattr(raw_expiry, 'year'):
        try:
            return datetime(
                raw_expiry.year,
                raw_expiry.month,
                raw_expiry.day,
                getattr(raw_expiry, 'hour', 0),
                getattr(raw_expiry, 'minute', 0),
                getattr(raw_expiry, 'second', 0),
            )
        except Exception:
            return None
    try:
        return datetime.fromisoformat(str(raw_expiry))
    except Exception:
        return None

