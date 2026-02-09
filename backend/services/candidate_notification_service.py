"""
Candidate Notification Service

Automates candidate communication and profile status updates based on HR actions.
Per the ATS spec: PROFILE_VIEWED, SHORTLISTED, NOT_SHORTLISTED.
"""

from typing import Tuple
from helpers.email_utils import send_notification_email

# Status display labels (spec)
STATUS_LABELS = {
    'profile_viewed': 'Profile Viewed',
    'shortlisted': 'Shortlisted',
    'rejected': 'Not Shortlisted',
}

# DB status values
STATUS_DB = {
    'profile_viewed': 'profile_viewed',
    'shortlisted': 'shortlisted',
    'rejected': 'rejected',
}


def _build_email_profile_viewed(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    company_name: str,
) -> Tuple[str, str]:
    """Email for PROFILE_VIEWED: inform candidate their profile has been reviewed."""
    subject = "Your profile has been reviewed"
    name = (candidate_name or '').strip() or 'there'
    body = (
        f"Hi {name},\n\n"
        f"Your profile has been reviewed for the {job_title or 'position'} role at {company_name or 'the company'}.\n\n"
        "The hiring team will contact you if they wish to move forward with your application.\n\n"
        "— Job Portal Team"
    )
    return subject, body


def _build_email_shortlisted(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    company_name: str,
) -> Tuple[str, str]:
    """Email for SHORTLISTED: inform candidate they are shortlisted; next steps will follow."""
    subject = "You have been shortlisted"
    name = (candidate_name or '').strip() or 'there'
    body = (
        f"Hi {name},\n\n"
        f"You have been shortlisted for the {job_title or 'position'} role at {company_name or 'the company'}.\n\n"
        "The hiring team will reach out with next steps in the coming days.\n\n"
        "— Job Portal Team"
    )
    return subject, body


def _build_email_not_shortlisted(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    company_name: str,
) -> Tuple[str, str]:
    """Email for NOT_SHORTLISTED: inform candidate they were not selected."""
    subject = "Update on your application"
    name = (candidate_name or '').strip() or 'there'
    body = (
        f"Hi {name},\n\n"
        f"Thank you for your interest in the {job_title or 'position'} role at {company_name or 'the company'}.\n\n"
        "After careful consideration, we have decided to move forward with other candidates for this position.\n\n"
        "We encourage you to apply for other roles that match your experience.\n\n"
        "— Job Portal Team"
    )
    return subject, body


def process_hr_action(
    hr_action: str,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    company_name: str,
    application_id: int,
    timestamp: str,
) -> dict:
    """
    Process HR action: generate email and return structured output.
    Does NOT send email or update DB; caller should do that.
    """
    hr_action = (hr_action or '').strip().upper()
    if hr_action == 'PROFILE_VIEWED':
        subject, body = _build_email_profile_viewed(
            candidate_name, candidate_email, job_title, company_name
        )
        status = 'profile_viewed'
    elif hr_action == 'SHORTLISTED':
        subject, body = _build_email_shortlisted(
            candidate_name, candidate_email, job_title, company_name
        )
        status = 'shortlisted'
    elif hr_action == 'NOT_SHORTLISTED':
        subject, body = _build_email_not_shortlisted(
            candidate_name, candidate_email, job_title, company_name
        )
        status = 'rejected'
    else:
        raise ValueError(f"Unknown hr_action: {hr_action}")

    label = STATUS_LABELS.get(status, status)
    return {
        "email": {
            "to": candidate_email,
            "subject": subject,
            "body": body,
        },
        "profile_update": {
            "application_id": str(application_id),
            "status": label,
            "status_db": status,
            "updated_at": timestamp,
        },
    }


def send_and_get_output(
    hr_action: str,
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    company_name: str,
    application_id: int,
    timestamp: str,
) -> dict:
    """Process HR action, send email, and return structured output."""
    if not candidate_email:
        raise ValueError("candidate_email is required")
    out = process_hr_action(
        hr_action, candidate_name, candidate_email, job_title, company_name,
        application_id, timestamp,
    )
    send_notification_email(
        out["email"]["to"],
        out["email"]["subject"],
        out["email"]["body"],
    )
    return out
