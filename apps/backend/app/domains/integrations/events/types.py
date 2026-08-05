"""Domain event type names (swap-ready for RabbitMQ/Kafka)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


JOB_CREATED = 'JobCreated'
JOB_UPDATED = 'JobUpdated'
JOB_CLOSED = 'JobClosed'
JOB_REPUBLISHED = 'JobRepublished'
PROVIDER_CONNECTED = 'ProviderConnected'
PROVIDER_DISCONNECTED = 'ProviderDisconnected'
PUBLISH_COMPLETED = 'PublishCompleted'
PUBLISH_FAILED = 'PublishFailed'
SYNC_COMPLETED = 'SyncCompleted'
SYNC_FAILED = 'SyncFailed'


@dataclass
class DomainEvent:
    event_type: str
    company_key: str | None = None
    job_id: str | None = None
    provider: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
