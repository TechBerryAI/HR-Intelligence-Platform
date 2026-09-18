"""Thin facade for Job module — no provider knowledge."""
from __future__ import annotations

import logging

from app.domains.integrations.company_context import company_key_from_job, resolve_organization_for_user
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
    organization_id: str | None = None,
    company_key: str | None = None,
    payload: dict | None = None,
) -> None:
    """Emit a domain event. Safe to call from Job routes; never raises to callers.

    organization_id is the tenant boundary used downstream to route
    publish/update/close work — it must come from the ``jobs`` row or the
    authenticated user's server-resolved org, never from a company name.
    """
    try:
        jid = job_id or (job or {}).get('jdid') or (job or {}).get('job_id')
        org_id = organization_id
        if not org_id and job:
            org_id = job.get('organization_id')
        if not org_id and user:
            org_id, _ = resolve_organization_for_user(user)
        key = company_key
        if not key and job:
            key = company_key_from_job(job)
        if not org_id or not jid:
            logger.debug('[integrations] skip event %s — missing organization_id/job_id', event_type)
            return
        get_event_bus().publish(
            DomainEvent(
                event_type=event_type,
                organization_id=str(org_id),
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


def emit_job_closed(
    job: dict | None = None,
    *,
    job_id: str | None = None,
    user: dict | None = None,
    organization_id: str | None = None,
    company_key: str | None = None,
) -> None:
    publish_job_lifecycle_event(
        JOB_CLOSED, job=job, job_id=job_id, user=user, organization_id=organization_id, company_key=company_key
    )
