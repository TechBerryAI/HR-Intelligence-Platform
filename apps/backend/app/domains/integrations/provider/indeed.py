"""Indeed provider — Current: mock placeholder. Future: Indeed Employer API."""
from __future__ import annotations

from app.domains.integrations.dto import (
    ConnectionResult,
    JobSnapshot,
    ProviderConfig,
    PublishResult,
    SyncResult,
)
from app.domains.integrations.mapper.indeed import to_indeed_payload
from app.domains.integrations.provider._mock import next_external_id
from app.domains.integrations.provider.base import JobProvider


class IndeedProvider(JobProvider):
    provider_type = 'indeed'
    id_prefix = 'ID'

    def publish(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        payload = to_indeed_payload(job)
        external_id = next_external_id(self.id_prefix)
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_id,
            external_status='published',
            message='Mock Indeed publish succeeded',
            payload={'request': payload, 'response': {'id': external_id}},
        )

    def update(self, job: JobSnapshot, external_job_id: str, config: ProviderConfig) -> PublishResult:
        payload = to_indeed_payload(job)
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status='updated',
            message='Mock Indeed update succeeded',
            payload={'request': payload, 'externalJobId': external_job_id},
        )

    def close(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status='closed',
            message='Mock Indeed close succeeded',
        )

    def sync_applications(self, config: ProviderConfig) -> SyncResult:
        return SyncResult(
            success=True,
            provider=self.provider_type,
            imported_count=0,
            message='Mock Indeed sync — no applications',
        )

    def test_connection(self, config: ProviderConfig) -> ConnectionResult:
        return ConnectionResult(
            success=True,
            provider=self.provider_type,
            message='Mock Indeed connection OK',
        )
