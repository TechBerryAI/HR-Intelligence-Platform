"""LinkedIn Job Posting API adapter (official Simple Job Postings).

Does not fake success. Live calls require LinkedIn Talent Solutions partner
access (OAuth 2.0 client-credentials) plus company apply URL.

Docs:
  https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/sync-job-postings
  CREATE duplicate of the same externalJobPostingId is dropped (not silent idempotent).
"""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote

import requests

from app.domains.integrations.dto import (
    ConnectionResult,
    JobSnapshot,
    ProviderConfig,
    PublishResult,
    SyncResult,
)
from app.domains.integrations.mapper.linkedin import (
    linkedin_external_posting_id,
    to_linkedin_payload,
)
from app.domains.integrations.provider.base import JobProvider
from app.domains.integrations.provider.credentials import (
    has_credentials,
    provider_access_connection,
    provider_access_publish,
)

logger = logging.getLogger(__name__)

_TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'
_POSTINGS_URL = 'https://api.linkedin.com/rest/simpleJobPostings'
_TASKS_URL = 'https://api.linkedin.com/rest/simpleJobPostingTasks'
_LINKEDIN_VERSION = '202603'
_PARTNER_DETAIL = (
    'LinkedIn Job Posting API requires Talent Solutions partner authorization. '
    'Apply at https://business.linkedin.com/talent-solutions/ats-partners/partner-application '
    'then configure Client ID/Secret, companyApplyUrl, and company URN.'
)
_DUPLICATE_MARKERS = (
    'partneridentifier already exists',
    'duplicate creation request',
    'duplicate job posting creation',
)

_token_cache: dict[str, tuple[str, float]] = {}


def _settings(config: ProviderConfig) -> dict[str, Any]:
    return dict(config.settings or {})


def _is_duplicate_create(text: str | None) -> bool:
    blob = (text or '').lower()
    return any(m in blob for m in _DUPLICATE_MARKERS)


class LinkedInProvider(JobProvider):
    provider_type = 'linkedin'
    id_prefix = 'LI'

    def publish(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        return self._operate(job, config, 'CREATE')

    def update(self, job: JobSnapshot, external_job_id: str, config: ProviderConfig) -> PublishResult:
        posting_id = (external_job_id or '').strip() or linkedin_external_posting_id(job.job_id)
        return self._operate(job, config, 'UPDATE', posting_id=posting_id)

    def close(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        posting_id = (external_job_id or '').strip()
        if not posting_id:
            return provider_access_publish(
                self.provider_type, 'externalJobPostingId is required to close a LinkedIn job'
            )
        job = None
        if posting_id.startswith('hcip:') and len(posting_id) <= 75:
            from app.domains.integrations.service.publish_service import load_job_snapshot

            job = load_job_snapshot(posting_id[5:], config.company_key)
        if job is None:
            job = JobSnapshot(
                job_id=posting_id,
                title='close',
                company=config.company or '',
                company_key=config.company_key or '',
            )
        return self._operate(job, config, 'CLOSE', posting_id=posting_id)

    def get_job_status(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        blocked = self._access_block(config, for_connection=False)
        if blocked:
            return blocked
        task_urn = (_settings(config).get('taskUrn') or '').strip()
        if not task_urn:
            return PublishResult(
                success=False,
                provider=self.provider_type,
                external_job_id=external_job_id,
                error=(
                    'LinkedIn job status requires a simpleJobPostingTask URN from the '
                    'CREATE/UPDATE/CLOSE response. Lookup by externalJobPostingId alone '
                    'is not documented on the Job Posting API.'
                ),
                message='Task URN required',
            )
        token, err = self._access_token(config)
        if err:
            return provider_access_publish(self.provider_type, err)
        ok, body, http_err = self._get_task(token, task_urn)
        if not ok:
            return PublishResult(
                success=False,
                provider=self.provider_type,
                external_job_id=external_job_id,
                error=http_err or 'Task status failed',
                payload={'response': body},
            )
        status = self._task_status(body, task_urn)
        return PublishResult(
            success=status in ('SUCCEEDED', 'PROCESSED'),
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status=status,
            message=status,
            payload={'response': body},
        )

    def reconcile_job(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        """Retry CREATE; treat documented duplicate-create as already posted."""
        return self._operate(job, config, 'CREATE')

    def sync_applications(self, config: ProviderConfig) -> SyncResult:
        return SyncResult(
            success=False,
            provider=self.provider_type,
            error='LinkedIn application sync is not implemented (separate Apply Connect / RSC APIs).',
            message='Not implemented',
        )

    def test_connection(self, config: ProviderConfig) -> ConnectionResult:
        blocked = self._access_block(config, for_connection=True)
        if blocked:
            return ConnectionResult(
                success=False,
                provider=self.provider_type,
                error=blocked.error,
                message=blocked.message,
            )
        token, err = self._access_token(config)
        if err or not token:
            return provider_access_connection(self.provider_type, err or _PARTNER_DETAIL)
        return ConnectionResult(
            success=True,
            provider=self.provider_type,
            message='LinkedIn OAuth token obtained. Job Posting API partner access still required to publish.',
        )

    def _access_block(self, config: ProviderConfig, *, for_connection: bool):
        if not has_credentials(config):
            return provider_access_connection(self.provider_type, _PARTNER_DETAIL) if for_connection else provider_access_publish(
                self.provider_type, _PARTNER_DETAIL
            )
        apply_url = (
            _settings(config).get('companyApplyUrl') or _settings(config).get('company_apply_url') or ''
        ).strip()
        if not apply_url and not for_connection:
            return provider_access_publish(
                self.provider_type,
                'companyApplyUrl is required by the LinkedIn Job Posting API (set it in provider settings).',
            )
        return None

    def _operate(
        self,
        job: JobSnapshot,
        config: ProviderConfig,
        operation: str,
        *,
        posting_id: str | None = None,
    ) -> PublishResult:
        blocked = self._access_block(config, for_connection=False)
        if blocked:
            return blocked
        try:
            payload = to_linkedin_payload(
                job, config, operation=operation, external_job_posting_id=posting_id
            )
        except ValueError as exc:
            return PublishResult(
                success=False, provider=self.provider_type, error=str(exc), message='Invalid payload'
            )
        correlation = payload['externalJobPostingId']
        if operation in ('CREATE', 'UPDATE') and not payload.get('location'):
            return PublishResult(
                success=False,
                provider=self.provider_type,
                error='location is required by the LinkedIn Job Posting API',
                message='Invalid payload',
            )
        token, err = self._access_token(config)
        if err or not token:
            return provider_access_publish(self.provider_type, err or _PARTNER_DETAIL)

        ok, body, http_err = self._batch_post(token, payload)
        blob = f'{http_err or ""} {body!s}'
        if operation == 'CREATE' and _is_duplicate_create(blob):
            return PublishResult(
                success=True,
                provider=self.provider_type,
                external_job_id=correlation,
                external_status='published',
                message='Reconciled: LinkedIn reported duplicate CREATE for this externalJobPostingId',
                payload={'request': payload, 'response': body, 'reconciled': True},
            )
        if not ok:
            return PublishResult(
                success=False,
                provider=self.provider_type,
                error=http_err or 'LinkedIn Job Posting API request failed',
                message='Publish failed',
                payload={'request': payload, 'response': body},
            )

        task_urn = self._extract_task_urn(body)
        if task_urn:
            t_ok, t_body, t_err = self._get_task(token, task_urn)
            status = self._task_status(t_body, task_urn) if t_ok else None
            combined = f'{t_err or ""} {t_body!s}'
            if operation == 'CREATE' and _is_duplicate_create(combined):
                return PublishResult(
                    success=True,
                    provider=self.provider_type,
                    external_job_id=correlation,
                    external_status='published',
                    message='Reconciled: LinkedIn dropped duplicate CREATE',
                    payload={'request': payload, 'response': body, 'task': t_body, 'reconciled': True},
                )
            if status in ('SUCCEEDED', 'PROCESSED') and not self._task_failed(t_body, task_urn):
                return PublishResult(
                    success=True,
                    provider=self.provider_type,
                    external_job_id=correlation,
                    external_status='closed' if operation == 'CLOSE' else 'published',
                    message=f'LinkedIn task {status}',
                    payload={'request': payload, 'response': body, 'task': t_body, 'taskUrn': task_urn},
                )
            if status == 'IN_PROGRESS':
                return PublishResult(
                    success=False,
                    provider=self.provider_type,
                    error='LinkedIn job posting task is still IN_PROGRESS; retry later',
                    message='Task in progress',
                    payload={'request': payload, 'response': body, 'task': t_body, 'taskUrn': task_urn},
                )
            if status == 'FAILED' or self._task_failed(t_body, task_urn):
                return PublishResult(
                    success=False,
                    provider=self.provider_type,
                    error=t_err or f'LinkedIn task FAILED for {operation}',
                    message='Task failed',
                    payload={'request': payload, 'response': body, 'task': t_body, 'taskUrn': task_urn},
                )

        # HTTP 200 on batch_create only means the task was accepted, not that the job is live.
        return PublishResult(
            success=False,
            provider=self.provider_type,
            error=(
                'LinkedIn accepted the request asynchronously but task status is not SUCCEEDED yet. '
                'Retry will poll or re-CREATE; duplicate CREATE is treated as already posted.'
            ),
            message='Awaiting LinkedIn task status',
            payload={'request': payload, 'response': body, 'taskUrn': task_urn},
        )

    def _access_token(self, config: ProviderConfig) -> tuple[str | None, str | None]:
        existing = (config.access_token or '').strip()
        if existing:
            return existing, None
        client_id = (config.client_id or '').strip()
        client_secret = (config.client_secret or '').strip()
        if not client_id or not client_secret:
            return None, _PARTNER_DETAIL
        cached = _token_cache.get(client_id)
        if cached and cached[1] > time.time():
            return cached[0], None
        try:
            resp = requests.post(
                _TOKEN_URL,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': client_id,
                    'client_secret': client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=20,
            )
        except requests.RequestException as exc:
            logger.warning('[linkedin] token request failed: %s', exc)
            return None, f'OAuth token request failed ({exc})'
        if resp.status_code >= 400:
            return None, (
                f'LinkedIn OAuth failed HTTP {resp.status_code}. {_PARTNER_DETAIL}'
            )
        try:
            data = resp.json()
        except ValueError:
            return None, 'LinkedIn OAuth returned a non-JSON body'
        token = (data.get('access_token') or '').strip()
        if not token:
            return None, 'LinkedIn OAuth response had no access_token'
        expires = int(data.get('expires_in') or 1800)
        _token_cache[client_id] = (token, time.time() + max(expires - 60, 60))
        return token, None

    def _headers(self, token: str) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'X-Restli-Method': 'batch_create',
            'LinkedIn-Version': _LINKEDIN_VERSION,
        }

    def _batch_post(self, token: str, element: dict[str, Any]) -> tuple[bool, Any, str | None]:
        try:
            resp = requests.post(
                _POSTINGS_URL,
                headers=self._headers(token),
                json={'elements': [element]},
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.warning('[linkedin] simpleJobPostings failed: %s', exc)
            return False, None, str(exc)
        try:
            body = resp.json() if resp.content else None
        except ValueError:
            body = {'raw': (resp.text or '')[:2000]}
        if resp.status_code >= 400:
            err = None
            if isinstance(body, dict):
                err = body.get('message') or body.get('error')
            return False, body, err or f'HTTP {resp.status_code}'
        return True, body, None

    def _get_task(self, token: str, task_urn: str) -> tuple[bool, Any, str | None]:
        url = f'{_TASKS_URL}?ids={quote(task_urn, safe="")}'
        headers = {
            'Authorization': f'Bearer {token}',
            'LinkedIn-Version': _LINKEDIN_VERSION,
        }
        try:
            resp = requests.get(url, headers=headers, timeout=20)
        except requests.RequestException as exc:
            return False, None, str(exc)
        try:
            body = resp.json() if resp.content else None
        except ValueError:
            body = {'raw': (resp.text or '')[:2000]}
        if resp.status_code >= 400:
            return False, body, f'HTTP {resp.status_code}'
        return True, body, None

    @staticmethod
    def _extract_task_urn(body: Any) -> str | None:
        if not isinstance(body, dict):
            return None
        elements = body.get('elements')
        if isinstance(elements, list) and elements:
            first = elements[0]
            if isinstance(first, dict):
                urn = first.get('id') or first.get('task')
                if urn:
                    return str(urn)
        return None

    @staticmethod
    def _task_entry(body: Any, task_urn: str) -> dict | None:
        if not isinstance(body, dict):
            return None
        results = body.get('results')
        if isinstance(results, dict):
            entry = results.get(task_urn)
            if isinstance(entry, dict):
                return entry
            for value in results.values():
                if isinstance(value, dict):
                    return value
        elements = body.get('elements')
        if isinstance(elements, list) and elements and isinstance(elements[0], dict):
            return elements[0]
        return body if body.get('status') else None

    def _task_status(self, body: Any, task_urn: str) -> str | None:
        entry = self._task_entry(body, task_urn)
        if not entry:
            return None
        return str(entry.get('status') or '') or None

    def _task_failed(self, body: Any, task_urn: str) -> bool:
        entry = self._task_entry(body, task_urn)
        if not entry:
            return False
        if str(entry.get('status') or '').upper() == 'FAILED':
            return True
        return bool(entry.get('errorMessage') or entry.get('error'))
