"""Thin facade for Job module — no provider knowledge."""
from __future__ import annotations

import logging

from app.domains.integrations.company_context import company_key_from_job, resolve_company_for_user
from app.domains.integrations.events.bus import get_event_bus
from app.domains.integrations.events.types import (
    JOB_CLOSED,
    JOB_CREATED,
    JOB_UPDATED,
    DomainEvent,
)

logger = logging.getLogger(__name__)


def publish_job_lifecycle_event(
    event_type: str,
    *,
    job: dict | None = None,
    job_id: str | None = None,
    user: dict | None = None,
    company_key: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emit a domain event. Safe to call from Job routes; never raises to callers."""
    try:
        jid = job_id or (job or {}).get('jdid') or (job or {}).get('job_id')
        key = company_key
        if not key and job:
            key = company_key_from_job(job)
        if not key and user:
            key, _ = resolve_company_for_user(user)
        if not key or not jid:
            logger.debug('[integrations] skip event %s — missing company_key/job_id', event_type)
            return
        get_event_bus().publish(
            DomainEvent(
                event_type=event_type,
                company_key=key,
                job_id=str(jid),
                payload=payload or {},
            )
        )
    except Exception:
        logger.exception('[integrations] failed to emit %s', event_type)


def emit_job_created(job: dict, user: dict | None = None) -> None:
    publish_job_lifecycle_event(JOB_CREATED, job=job, user=user)


def emit_job_updated(job: dict, user: dict | None = None) -> None:
    publish_job_lifecycle_event(JOB_UPDATED, job=job, user=user)


def emit_job_closed(job: dict | None = None, *, job_id: str | None = None, user: dict | None = None, company_key: str | None = None) -> None:
    publish_job_lifecycle_event(JOB_CLOSED, job=job, job_id=job_id, user=user, company_key=company_key)
