"""
Canonical application status values for PostgreSQL (applications_status_check).
All writes to applications.status must use these constants.
"""

from __future__ import annotations

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

# Terminal statuses cannot be overwritten (Withdrawn stays terminal; Hired is terminal).
TERMINAL_STATUSES = frozenset({STATUS_HIRED, STATUS_WITHDRAWN})

# Allowed recruiter/workflow transitions (canonical names).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_APPLIED: frozenset({STATUS_SHORTLISTED, STATUS_REJECTED}),
    STATUS_SCREENING: frozenset({STATUS_SHORTLISTED, STATUS_REJECTED}),
    STATUS_MATCHED: frozenset({STATUS_SHORTLISTED, STATUS_REJECTED}),
    STATUS_SHORTLISTED: frozenset({STATUS_INTERVIEW, STATUS_REJECTED}),
    STATUS_INTERVIEW: frozenset({STATUS_OFFER, STATUS_REJECTED, STATUS_SHORTLISTED}),
    STATUS_OFFER: frozenset({STATUS_HIRED, STATUS_REJECTED}),
    STATUS_REJECTED: frozenset(),
    STATUS_HIRED: frozenset(),
    STATUS_WITHDRAWN: frozenset(),
}


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


def is_terminal(status: str | None) -> bool:
    return normalize_status(status) in TERMINAL_STATUSES


def allowed_next_statuses(from_status: str | None) -> frozenset[str]:
    current = normalize_status(from_status)
    return ALLOWED_TRANSITIONS.get(current, frozenset())


def can_transition(from_status: str | None, to_status: str | None) -> bool:
    """
    Return True if moving from_status -> to_status is allowed.
    Same-status is a no-op (allowed). Hired and Withdrawn cannot leave.
    """
    if to_status is None or str(to_status).strip() == '':
        return False
    current = normalize_status(from_status)
    # Do not normalize target via legacy map alone if it is already canonical;
    # still accept legacy aliases for the destination.
    target = normalize_status(to_status)
    if target not in ALLOWED_STATUSES:
        return False
    if current == target:
        return True
    if current in TERMINAL_STATUSES:
        return False
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def status_after_ats(shortlisted: bool) -> str:
    return STATUS_SHORTLISTED if shortlisted else STATUS_REJECTED
