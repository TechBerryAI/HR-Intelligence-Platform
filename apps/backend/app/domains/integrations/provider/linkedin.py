"""LinkedIn job-board adapter. Current: credentials + staging publish. Future: LinkedIn Jobs API + OAuth."""
from __future__ import annotations

from app.domains.integrations.dto import (
    ConnectionResult,
    JobSnapshot,
    ProviderConfig,
    PublishResult,
    SyncResult,
)
from app.domains.integrations.mapper.linkedin import to_linkedin_payload
from app.domains.integrations.provider.base import JobProvider
from app.domains.integrations.provider.credentials import (
    credentials_missing_connection,
    credentials_missing_publish,
    has_credentials,
)
from app.domains.integrations.provider.external_ids import next_external_id


class LinkedInProvider(JobProvider):
    provider_type = 'linkedin'
    id_prefix = 'LI'

    def publish(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        if not has_credentials(config):
            return credentials_missing_publish(self.provider_type)
        payload = to_linkedin_payload(job)
        external_id = next_external_id(self.id_prefix)
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_id,
            external_status='published',
            message='Job published successfully',
            payload={'request': payload, 'response': {'id': external_id}},
        )

    def update(self, job: JobSnapshot, external_job_id: str, config: ProviderConfig) -> PublishResult:
        if not has_credentials(config):
            return credentials_missing_publish(self.provider_type)
        payload = to_linkedin_payload(job)
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status='updated',
            message='Job updated successfully',
            payload={'request': payload, 'externalJobId': external_job_id},
        )

    def close(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        if not has_credentials(config):
            return credentials_missing_publish(self.provider_type)
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status='closed',
            message='Job closed successfully',
        )

    def sync_applications(self, config: ProviderConfig) -> SyncResult:
        if not has_credentials(config):
            return SyncResult(
                success=False,
                provider=self.provider_type,
                error='Credentials required to sync applications',
                message='Credentials required',
            )
        return SyncResult(
            success=True,
            provider=self.provider_type,
            imported_count=0,
            message='Sync completed — no new applications',
        )

    def test_connection(self, config: ProviderConfig) -> ConnectionResult:
        if not has_credentials(config):
            return credentials_missing_connection(self.provider_type)
        return ConnectionResult(
            success=True,
            provider=self.provider_type,
            message='Connection verified',
        )
