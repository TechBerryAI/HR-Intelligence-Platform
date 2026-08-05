"""LinkedIn provider — Current: mock placeholder. Future: LinkedIn Jobs API + OAuth."""
from __future__ import annotations

from app.domains.integrations.dto import (
    ConnectionResult,
    JobSnapshot,
    ProviderConfig,
    PublishResult,
    SyncResult,
)
from app.domains.integrations.mapper.linkedin import to_linkedin_payload
from app.domains.integrations.provider._mock import next_external_id
from app.domains.integrations.provider.base import JobProvider


class LinkedInProvider(JobProvider):
    provider_type = 'linkedin'
    id_prefix = 'LI'

    def publish(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        payload = to_linkedin_payload(job)
        external_id = next_external_id(self.id_prefix)
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_id,
            external_status='published',
            message='Mock LinkedIn publish succeeded',
            payload={'request': payload, 'response': {'id': external_id}},
        )

    def update(self, job: JobSnapshot, external_job_id: str, config: ProviderConfig) -> PublishResult:
        payload = to_linkedin_payload(job)
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_id,
            external_status='updated',
            message='Mock LinkedIn update succeeded',
            payload={'request': payload, 'externalJobId': external_job_id},
        )

    def close(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status='closed',
            message='Mock LinkedIn close succeeded',
        )

    def sync_applications(self, config: ProviderConfig) -> SyncResult:
        return SyncResult(
            success=True,
            provider=self.provider_type,
            imported_count=0,
            message='Mock LinkedIn sync — no applications',
        )

    def test_connection(self, config: ProviderConfig) -> ConnectionResult:
        return ConnectionResult(
            success=True,
            provider=self.provider_type,
            message='Mock LinkedIn connection OK',
        )
