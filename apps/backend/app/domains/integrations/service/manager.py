"""IntegrationManagerService — routes operations to enabled providers."""
from __future__ import annotations

import logging
import time
from typing import Iterable

from app.domains.integrations.dto import (
    AggregatePublishResult,
    ConnectionResult,
    JobSnapshot,
    ProviderConfig,
    PublishResult,
    SyncResult,
)
from app.domains.integrations.provider.factory import ensure_default_providers, get_provider
from app.domains.integrations import repository as repo
from app.domains.integrations.service.serializers import row_to_provider_config

logger = logging.getLogger(__name__)


def _log_call(
    company_key: str,
    provider: str,
    operation: str,
    status: str,
    *,
    job_id: str | None = None,
    external_job_id: str | None = None,
    request_payload=None,
    response_payload=None,
    execution_time_ms: int | None = None,
    retry_count: int = 0,
    error_message: str | None = None,
):
    try:
        repo.insert_sync_log(
            company_key,
            provider,
            operation,
            status,
            job_id=job_id,
            external_job_id=external_job_id,
            request_payload=request_payload,
            response_payload=response_payload,
            execution_time_ms=execution_time_ms,
            retry_count=retry_count,
            error_message=error_message,
        )
    except Exception as exc:
        logger.warning('[integrations] sync_log insert failed: %s', exc)


class IntegrationManagerService:
    """Discover enabled providers and aggregate publish/update/close/sync results."""

    def __init__(self):
        ensure_default_providers()

    def _configs_for(
        self,
        company_key: str,
        providers: Iterable[str] | None = None,
        *,
        enabled_only: bool = True,
        auto_publish_only: bool = False,
    ) -> list[ProviderConfig]:
        if auto_publish_only:
            rows = repo.list_enabled_auto_publish(company_key)
        elif enabled_only:
            rows = repo.list_enabled_providers(company_key)
        else:
            rows = repo.list_providers(company_key)
        configs = [row_to_provider_config(r) for r in rows]
        configs = [c for c in configs if c]
        if providers:
            wanted = {p.strip().lower() for p in providers if p}
            configs = [c for c in configs if c.provider in wanted]
        return configs

    def publish_job(
        self,
        job: JobSnapshot,
        *,
        providers: list[str] | None = None,
        auto_publish_only: bool = False,
        retry_count: int = 0,
    ) -> AggregatePublishResult:
        configs = self._configs_for(
            job.company_key,
            providers,
            enabled_only=True,
            auto_publish_only=auto_publish_only,
        )
        results: list[PublishResult] = []
        for config in configs:
            results.append(self._publish_one(job, config, retry_count=retry_count))
        return AggregatePublishResult(job_id=job.job_id, results=results)

    def _publish_one(self, job: JobSnapshot, config: ProviderConfig, *, retry_count: int = 0) -> PublishResult:
        provider = get_provider(config.provider)
        if not provider:
            result = PublishResult(
                success=False,
                provider=config.provider,
                error=f'Unknown provider: {config.provider}',
            )
            self._persist_external(job, config.provider, result, retry_count=retry_count)
            return result

        existing = repo.get_external_job(job.job_id, config.provider)
        start = time.perf_counter()
        try:
            if existing and existing.get('external_job_id') and existing.get('sync_status') not in ('dead', 'failed', 'closed'):
                result = provider.update(job, existing['external_job_id'], config)
            else:
                result = provider.publish(job, config)
        except Exception as exc:
            logger.exception('[integrations] publish failed for %s', config.provider)
            result = PublishResult(success=False, provider=config.provider, error=str(exc))
        ms = int((time.perf_counter() - start) * 1000)
        _log_call(
            job.company_key,
            config.provider,
            'publish',
            'success' if result.success else 'failed',
            job_id=job.job_id,
            external_job_id=result.external_job_id,
            request_payload=job.to_dict(),
            response_payload=result.to_dict(),
            execution_time_ms=ms,
            retry_count=retry_count,
            error_message=result.error,
        )
        self._persist_external(job, config.provider, result, retry_count=retry_count)
        return result

    def update_job(
        self,
        job: JobSnapshot,
        *,
        providers: list[str] | None = None,
        retry_count: int = 0,
    ) -> AggregatePublishResult:
        configs = self._configs_for(job.company_key, providers, enabled_only=True)
        results: list[PublishResult] = []
        for config in configs:
            existing = repo.get_external_job(job.job_id, config.provider)
            if not existing or not existing.get('external_job_id'):
                results.append(self._publish_one(job, config, retry_count=retry_count))
                continue
            provider = get_provider(config.provider)
            if not provider:
                results.append(PublishResult(success=False, provider=config.provider, error='Unknown provider'))
                continue
            start = time.perf_counter()
            try:
                result = provider.update(job, existing['external_job_id'], config)
            except Exception as exc:
                result = PublishResult(success=False, provider=config.provider, error=str(exc))
            ms = int((time.perf_counter() - start) * 1000)
            _log_call(
                job.company_key,
                config.provider,
                'update',
                'success' if result.success else 'failed',
                job_id=job.job_id,
                external_job_id=result.external_job_id or existing.get('external_job_id'),
                request_payload=job.to_dict(),
                response_payload=result.to_dict(),
                execution_time_ms=ms,
                retry_count=retry_count,
                error_message=result.error,
            )
            self._persist_external(job, config.provider, result, retry_count=retry_count)
            results.append(result)
        return AggregatePublishResult(job_id=job.job_id, results=results)

    def close_job(
        self,
        company_key: str,
        job_id: str,
        *,
        providers: list[str] | None = None,
        retry_count: int = 0,
    ) -> AggregatePublishResult:
        externals = repo.list_external_jobs(company_key, job_id=job_id)
        if providers:
            wanted = {p.strip().lower() for p in providers}
            externals = [e for e in externals if e.get('provider') in wanted]
        results: list[PublishResult] = []
        for row in externals:
            provider_name = row.get('provider')
            external_id = row.get('external_job_id')
            if not external_id:
                continue
            provider = get_provider(provider_name)
            config_row = repo.get_provider_row(company_key, provider_name)
            config = row_to_provider_config(config_row) or ProviderConfig(
                id=None, company_key=company_key, company=None, provider=provider_name
            )
            start = time.perf_counter()
            if not provider:
                result = PublishResult(success=False, provider=provider_name, error='Unknown provider')
            else:
                try:
                    result = provider.close(external_id, config)
                except Exception as exc:
                    result = PublishResult(success=False, provider=provider_name, error=str(exc))
            ms = int((time.perf_counter() - start) * 1000)
            _log_call(
                company_key,
                provider_name,
                'close',
                'success' if result.success else 'failed',
                job_id=job_id,
                external_job_id=external_id,
                response_payload=result.to_dict(),
                execution_time_ms=ms,
                retry_count=retry_count,
                error_message=result.error,
            )
            repo.upsert_external_job(
                company_key,
                job_id,
                provider_name,
                external_job_id=external_id,
                external_status=result.external_status or 'closed',
                sync_status='closed' if result.success else 'failed',
                error_message=result.error,
                retry_count=retry_count,
                response_payload=result.to_dict(),
            )
            results.append(result)
        return AggregatePublishResult(job_id=job_id, results=results)

    def test_connection(self, company_key: str, provider_name: str) -> ConnectionResult:
        ensure_default_providers()
        provider = get_provider(provider_name)
        if not provider:
            return ConnectionResult(success=False, provider=provider_name, error='Unknown provider')
        row = repo.get_provider_row(company_key, provider_name)
        config = row_to_provider_config(row) or ProviderConfig(
            id=None, company_key=company_key, company=None, provider=provider_name
        )
        start = time.perf_counter()
        try:
            result = provider.test_connection(config)
        except Exception as exc:
            result = ConnectionResult(success=False, provider=provider_name, error=str(exc))
        ms = int((time.perf_counter() - start) * 1000)
        _log_call(
            company_key,
            provider_name,
            'test_connection',
            'success' if result.success else 'failed',
            response_payload=result.to_dict(),
            execution_time_ms=ms,
            error_message=result.error,
        )
        return result

    def sync_provider(self, company_key: str, provider_name: str) -> SyncResult:
        ensure_default_providers()
        provider = get_provider(provider_name)
        if not provider:
            return SyncResult(success=False, provider=provider_name, error='Unknown provider')
        row = repo.get_provider_row(company_key, provider_name)
        config = row_to_provider_config(row) or ProviderConfig(
            id=None, company_key=company_key, company=None, provider=provider_name
        )
        start = time.perf_counter()
        imported = 0
        try:
            # Sync per published external job when HTTP adapter exposes detailed sync
            from app.domains.integrations.provider.generic import GenericHttpProvider

            if isinstance(provider, GenericHttpProvider):
                externals = repo.list_external_jobs(company_key)
                externals = [e for e in externals if e.get('provider') == provider_name and e.get('external_job_id')]
                if not externals:
                    result, apps = provider.sync_applications_detailed(config)
                    imported = self._persist_applications(
                        company_key, provider_name, apps, job_id=None, external_job_id=None
                    )
                    result.imported_count = imported
                else:
                    errors = []
                    for ext in externals:
                        result_one, apps = provider.sync_applications_detailed(
                            config, external_job_id=ext.get('external_job_id')
                        )
                        if not result_one.success:
                            errors.append(result_one.error or 'sync failed')
                            continue
                        imported += self._persist_applications(
                            company_key,
                            provider_name,
                            apps,
                            job_id=ext.get('job_id'),
                            external_job_id=ext.get('external_job_id'),
                        )
                    result = SyncResult(
                        success=len(errors) == 0,
                        provider=provider_name,
                        imported_count=imported,
                        message=f'Sync completed — {imported} application(s)',
                        error='; '.join(errors) if errors else None,
                    )
            else:
                result = provider.sync_applications(config)
        except Exception as exc:
            result = SyncResult(success=False, provider=provider_name, error=str(exc))
        ms = int((time.perf_counter() - start) * 1000)
        _log_call(
            company_key,
            provider_name,
            'sync',
            'success' if result.success else 'failed',
            response_payload=result.to_dict(),
            execution_time_ms=ms,
            error_message=result.error,
        )
        return result

    def _persist_applications(
        self,
        company_key: str,
        provider_name: str,
        apps: list,
        *,
        job_id: str | None,
        external_job_id: str | None,
    ) -> int:
        count = 0
        for app in apps or []:
            app_id = app.get('externalApplicationId')
            if not app_id:
                continue
            repo.upsert_external_application(
                company_key,
                provider_name,
                str(app_id),
                job_id=job_id,
                external_job_id=external_job_id,
                candidate_email=app.get('candidateEmail'),
                candidate_name=app.get('candidateName'),
                mapped_status=app.get('status'),
                payload=app.get('raw') or app,
            )
            count += 1
        return count

    def _persist_external(
        self,
        job: JobSnapshot,
        provider_name: str,
        result: PublishResult,
        *,
        retry_count: int = 0,
    ) -> None:
        sync_status = 'published' if result.success else 'failed'
        if result.external_status == 'closed':
            sync_status = 'closed'
        repo.upsert_external_job(
            job.company_key,
            job.job_id,
            provider_name,
            external_job_id=result.external_job_id,
            external_status=result.external_status,
            sync_status=sync_status,
            error_message=result.error,
            retry_count=retry_count,
            request_payload=job.to_dict(),
            response_payload=result.to_dict(),
            mark_published=result.success,
        )
