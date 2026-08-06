"""Safe trigger for interview scheduling after Shortlisted."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def trigger_interview_scheduling(application_id: int | None, recruiter_hrid: str | None = None) -> None:
    """Never raise into the shortlist request path."""
    if not application_id:
        return
    try:
        from app.domains.recruitment.services import interview_scheduling_service as scheduling

        result = scheduling.on_shortlisted(int(application_id), recruiter_hrid=recruiter_hrid)
        logger.info(
            '[interview_scheduling] trigger app=%s recruiter=%s result=%s',
            application_id,
            recruiter_hrid,
            result,
        )
    except Exception:
        logger.exception(
            '[interview_scheduling] trigger failed app=%s',
            application_id,
        )
