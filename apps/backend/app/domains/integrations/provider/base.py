"""JobProvider plugin contract."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.domains.integrations.dto import (
    ConnectionResult,
    JobSnapshot,
    ProviderConfig,
    PublishResult,
    SyncResult,
)


class JobProvider(ABC):
    """Provider-agnostic job board / ATS distribution adapter."""

    provider_type: str = ''
    id_prefix: str = ''

    @abstractmethod
    def publish(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        ...

    @abstractmethod
    def update(self, job: JobSnapshot, external_job_id: str, config: ProviderConfig) -> PublishResult:
        ...

    @abstractmethod
    def close(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        ...

    def get_job_status(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        return PublishResult(
            success=False,
            provider=self.provider_type,
            external_job_id=external_job_id,
            error='get_job_status is not supported for this provider',
            message='Not supported',
        )

    def reconcile_job(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        return PublishResult(
            success=False,
            provider=self.provider_type,
            error='reconcile_job is not supported for this provider',
            message='Not supported',
        )

    @abstractmethod
    def sync_applications(self, config: ProviderConfig) -> SyncResult:
        ...

    @abstractmethod
    def test_connection(self, config: ProviderConfig) -> ConnectionResult:
        ...
