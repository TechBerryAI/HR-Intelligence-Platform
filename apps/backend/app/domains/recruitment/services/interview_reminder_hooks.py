"""Future reminder worker hooks — no-op stubs for now."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def on_invite_sent(interview_id: str) -> None:
    """Hook for future reminder workers when an interview invite is sent."""
    logger.debug('[interview_reminders] on_invite_sent interview_id=%s (stub)', interview_id)


def on_interview_scheduled(interview_id: str) -> None:
    """Hook for future reminder workers when an interview is booked."""
    logger.debug('[interview_reminders] on_interview_scheduled interview_id=%s (stub)', interview_id)
