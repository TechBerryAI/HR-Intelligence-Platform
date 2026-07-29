"""
Canonical application status values for PostgreSQL (applications_status_check).
All writes to applications.status must use these constants.
"""

STATUS_APPLIED = 'Applied'
STATUS_SCREENING = 'Screening'
STATUS_MATCHED = 'Matched'
STATUS_SHORTLISTED = 'Shortlisted'
STATUS_INTERVIEW = 'Interview'
STATUS_REJECTED = 'Rejected'
STATUS_OFFER = 'Offer'
STATUS_HIRED = 'Hired'
STATUS_WITHDRAWN = 'Withdrawn'

ALLOWED_STATUSES = frozenset({
    STATUS_APPLIED,
    STATUS_SCREENING,
    STATUS_MATCHED,
    STATUS_SHORTLISTED,
    STATUS_INTERVIEW,
    STATUS_REJECTED,
    STATUS_OFFER,
    STATUS_HIRED,
    STATUS_WITHDRAWN,
})


def normalize_status(value: str | None) -> str:
    """Map legacy/lowercase status strings to canonical PostgreSQL values."""
    if not value:
        return STATUS_APPLIED
    key = str(value).strip().lower()
    mapping = {
        'pending': STATUS_APPLIED,
        'applied': STATUS_APPLIED,
        'profile_viewed': STATUS_SCREENING,
        'screening': STATUS_SCREENING,
        'matched': STATUS_MATCHED,
        'shortlisted': STATUS_SHORTLISTED,
        'interview': STATUS_INTERVIEW,
        'rejected': STATUS_REJECTED,
        'not_shortlisted': STATUS_REJECTED,
        'offer': STATUS_OFFER,
        'hired': STATUS_HIRED,
        'withdrawn': STATUS_WITHDRAWN,
        'ats_failed': STATUS_APPLIED,
    }
    if key in mapping:
        return mapping[key]
    if value in ALLOWED_STATUSES:
        return value
    return STATUS_APPLIED


def status_after_ats(shortlisted: bool) -> str:
    return STATUS_SHORTLISTED if shortlisted else STATUS_REJECTED
