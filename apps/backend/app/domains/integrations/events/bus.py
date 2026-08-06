"""In-process event bus — replaceable with a message broker later."""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Callable

from app.domains.integrations.events.types import DomainEvent
from app.domains.integrations import repository as repo

logger = logging.getLogger(__name__)

Handler = Callable[[DomainEvent], None]


class InProcessEventBus:
    def __init__(self):
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Handler) -> None:
        with self._lock:
            self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        try:
            repo.insert_provider_event(
                event.event_type,
                company_key=event.company_key,
                job_id=event.job_id,
                provider=event.provider,
                payload=event.payload,
                status='dispatched',
            )
        except Exception as exc:
            logger.warning('[integrations] provider_events insert failed: %s', exc)

        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))
            # Also notify wildcard subscribers
            handlers.extend(self._handlers.get('*', []))

        for handler in handlers:
            try:
                handler(event)
            except Exception:
                logger.exception('[integrations] event handler failed for %s', event.event_type)


_bus: InProcessEventBus | None = None
_bus_lock = threading.Lock()


def get_event_bus() -> InProcessEventBus:
    global _bus
    with _bus_lock:
        if _bus is None:
            _bus = InProcessEventBus()
        return _bus
