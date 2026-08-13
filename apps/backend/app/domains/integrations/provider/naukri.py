"""Naukri job-board adapter.

There is no public Naukri Job Posting API in this project. Enterprise posting
goes through Naukri Amplify / account-manager partner programs. This adapter
never reports a successful remote publish.
"""
from __future__ import annotations

from app.domains.integrations.dto import (
    ConnectionResult,
    JobSnapshot,
    ProviderConfig,
    PublishResult,
    SyncResult,
)
from app.domains.integrations.provider.base import JobProvider
from app.domains.integrations.provider.credentials import (
    provider_access_connection,
    provider_access_publish,
)

_NAUKRI_DETAIL = (
    'Naukri has no public job-posting API in this codebase. '
    'Remote publish requires a Naukri Amplify / partner integration from your Naukri account manager.'
)


class NaukriProvider(JobProvider):
    provider_type = 'naukri'
    id_prefix = 'NK'

    def publish(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        return provider_access_publish(self.provider_type, _NAUKRI_DETAIL)

    def update(self, job: JobSnapshot, external_job_id: str, config: ProviderConfig) -> PublishResult:
        return provider_access_publish(self.provider_type, _NAUKRI_DETAIL)

    def close(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        return provider_access_publish(self.provider_type, _NAUKRI_DETAIL)

    def get_job_status(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        return provider_access_publish(self.provider_type, _NAUKRI_DETAIL)

    def reconcile_job(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        return provider_access_publish(self.provider_type, _NAUKRI_DETAIL)

    def sync_applications(self, config: ProviderConfig) -> SyncResult:
        return SyncResult(
            success=False,
            provider=self.provider_type,
            error=_NAUKRI_DETAIL,
            message='PROVIDER ACCESS REQUIRED',
        )

    def test_connection(self, config: ProviderConfig) -> ConnectionResult:
        return provider_access_connection(self.provider_type, _NAUKRI_DETAIL)
