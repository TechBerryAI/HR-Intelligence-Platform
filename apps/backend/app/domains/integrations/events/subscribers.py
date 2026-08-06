"""Subscribe integration handlers to job lifecycle events."""
from __future__ import annotations

import logging

from app.domains.integrations.events.bus import get_event_bus
from app.domains.integrations.events.types import (
    JOB_CLOSED,
    JOB_CREATED,
    JOB_REPUBLISHED,
    JOB_UPDATED,
    DomainEvent,
)
from app.domains.integrations.service import publish_service

logger = logging.getLogger(__name__)

_subscribed = False


def _on_job_created(event: DomainEvent) -> None:
    if not event.company_key or not event.job_id:
        return
    # Mode 1: auto-publish to providers with auto_publish enabled
    publish_service.enqueue_publish(
        event.company_key,
        event.job_id,
        auto_publish_only=True,
        operation='publish',
    )


def _on_job_updated(event: DomainEvent) -> None:
    if not event.company_key or not event.job_id:
        return
    publish_service.enqueue_update(event.company_key, event.job_id)


def _on_job_closed(event: DomainEvent) -> None:
    if not event.company_key or not event.job_id:
        return
    publish_service.enqueue_close(event.company_key, event.job_id)


def _on_job_republished(event: DomainEvent) -> None:
    if not event.company_key or not event.job_id:
        return
    providers = (event.payload or {}).get('providers')
    publish_service.enqueue_publish(
        event.company_key,
        event.job_id,
        providers=providers,
        auto_publish_only=False,
        operation='republish',
    )


def register_subscribers() -> None:
    global _subscribed
    if _subscribed:
        return
    bus = get_event_bus()
    bus.subscribe(JOB_CREATED, _on_job_created)
    bus.subscribe(JOB_UPDATED, _on_job_updated)
    bus.subscribe(JOB_CLOSED, _on_job_closed)
    bus.subscribe(JOB_REPUBLISHED, _on_job_republished)
    _subscribed = True
    logger.info('[integrations] event subscribers registered')
