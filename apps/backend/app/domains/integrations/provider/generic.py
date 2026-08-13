"""HTTP job-board adapter driven by settings_json (baseUrl + endpoints)."""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urljoin

import requests

from app.domains.integrations.dto import (
    ConnectionResult,
    JobSnapshot,
    ProviderConfig,
    PublishResult,
    SyncResult,
)
from app.domains.integrations.provider.base import JobProvider
from app.domains.integrations.provider.credentials import (
    credentials_missing_connection,
    credentials_missing_publish,
    has_credentials,
)

logger = logging.getLogger(__name__)

_ENDPOINT_KEYS = ('test', 'publish', 'update', 'close', 'applications', 'status')


def parse_endpoint(spec: str | None) -> tuple[str, str] | None:
    """Parse 'GET /path' or '/path' (defaults to GET) into (method, path)."""
    if not spec or not str(spec).strip():
        return None
    s = str(spec).strip()
    m = re.match(r'^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$', s, re.I)
    if m:
        return m.group(1).upper(), m.group(2).strip()
    return 'GET', s


def to_job_payload(job: JobSnapshot, provider: str) -> dict[str, Any]:
    return {
        'provider': provider,
        'title': job.title,
        'company': job.company,
        'location': job.location,
        'description': job.description,
        'salary': job.salary,
        'experience': job.experience,
        'keywords': job.keywords,
        'referenceId': job.job_id,
        'jobId': job.job_id,
    }


def _extract_id(data: Any) -> str | None:
    if data is None:
        return None
    if isinstance(data, (str, int)):
        return str(data)
    if isinstance(data, dict):
        for key in ('id', 'jobId', 'job_id', 'externalJobId', 'external_job_id', 'applicationId'):
            if data.get(key) is not None:
                return str(data[key])
        # nested data
        for nest in ('data', 'result', 'job', 'application'):
            if isinstance(data.get(nest), dict):
                found = _extract_id(data[nest])
                if found:
                    return found
    return None


def normalize_applications(payload: Any) -> list[dict[str, Any]]:
    """Normalize provider application list into internal shape."""
    items: list = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ('applications', 'data', 'items', 'results', 'candidates'):
            if isinstance(payload.get(key), list):
                items = payload[key]
                break
        if not items and payload.get('id'):
            items = [payload]

    out: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        app_id = (
            raw.get('id')
            or raw.get('applicationId')
            or raw.get('externalApplicationId')
            or raw.get('application_id')
        )
        if app_id is None:
            continue
        out.append({
            'externalApplicationId': str(app_id),
            'candidateEmail': raw.get('email') or raw.get('candidateEmail') or raw.get('candidate_email'),
            'candidateName': raw.get('name') or raw.get('candidateName') or raw.get('candidate_name'),
            'status': raw.get('status') or raw.get('applicationStatus'),
            'appliedAt': raw.get('appliedAt') or raw.get('applied_at') or raw.get('createdAt'),
            'raw': raw,
        })
    return out


class GenericHttpProvider(JobProvider):
    """Custom platform adapter — real HTTP using company settings_json."""

    def __init__(self, provider_type: str, display_name: str | None = None):
        self.provider_type = (provider_type or '').strip().lower()
        self.id_prefix = (self.provider_type[:2] or 'XB').upper()
        self.display_name = display_name or self.provider_type.title()

    def _settings(self, config: ProviderConfig) -> dict[str, Any]:
        return dict(config.settings or {})

    def _base_url(self, config: ProviderConfig) -> str:
        return (self._settings(config).get('baseUrl') or self._settings(config).get('base_url') or '').rstrip('/')

    def _endpoints(self, config: ProviderConfig) -> dict[str, str]:
        eps = self._settings(config).get('endpoints') or {}
        return eps if isinstance(eps, dict) else {}

    def _headers(self, config: ProviderConfig) -> dict[str, str]:
        settings = self._settings(config)
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        auth_mode = (settings.get('authHeader') or settings.get('auth_header') or 'Bearer').strip()
        extra = settings.get('headers') if isinstance(settings.get('headers'), dict) else {}
        headers.update({str(k): str(v) for k, v in extra.items()})

        token = (config.access_token or '').strip()
        client_id = (config.client_id or '').strip()
        client_secret = (config.client_secret or '').strip()

        if token:
            if auth_mode.lower() == 'raw':
                headers['Authorization'] = token
            else:
                headers['Authorization'] = f'{auth_mode} {token}'.strip()
        elif client_id and client_secret:
            import base64

            if (settings.get('authType') or config.auth_type or '').lower() == 'basic':
                encoded = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
                headers['Authorization'] = f'Basic {encoded}'
            else:
                headers['X-Client-Id'] = client_id
                headers['X-Client-Secret'] = client_secret
                if settings.get('apiKeyHeader'):
                    headers[str(settings['apiKeyHeader'])] = client_secret
        return headers

    def _request(
        self,
        config: ProviderConfig,
        endpoint_key: str,
        *,
        path_vars: dict[str, str] | None = None,
        json_body: Any = None,
        timeout: float = 30.0,
    ) -> tuple[bool, Any, str | None, int | None]:
        base = self._base_url(config)
        if not base:
            return False, None, 'API Base URL is required in platform settings', None
        spec = self._endpoints(config).get(endpoint_key)
        parsed = parse_endpoint(spec)
        if not parsed:
            # Fallback for test: GET base URL
            if endpoint_key == 'test':
                method, path = 'GET', '/'
            else:
                return False, None, f'Endpoint "{endpoint_key}" is not configured', None
        else:
            method, path = parsed

        for k, v in (path_vars or {}).items():
            path = path.replace('{' + k + '}', str(v))

        if path.startswith('http://') or path.startswith('https://'):
            url = path
        else:
            url = urljoin(base + '/', path.lstrip('/'))

        try:
            resp = requests.request(
                method,
                url,
                headers=self._headers(config),
                json=json_body if method in ('POST', 'PUT', 'PATCH') else None,
                timeout=timeout,
            )
            try:
                body = resp.json() if resp.content else None
            except ValueError:
                body = {'raw': resp.text[:2000]} if resp.text else None
            if resp.status_code >= 400:
                err = None
                if isinstance(body, dict):
                    err = body.get('error') or body.get('message')
                return False, body, err or f'HTTP {resp.status_code}', resp.status_code
            return True, body, None, resp.status_code
        except requests.Timeout:
            return False, None, 'Request timed out', None
        except requests.RequestException as exc:
            logger.warning('[integrations] HTTP error %s: %s', self.provider_type, exc)
            return False, None, str(exc), None

    def publish(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        if not has_credentials(config):
            return credentials_missing_publish(self.provider_type)
        ok, body, err, _ = self._request(
            config, 'publish', json_body=to_job_payload(job, self.provider_type)
        )
        if not ok:
            return PublishResult(
                success=False,
                provider=self.provider_type,
                error=err or 'Publish failed',
                message='Publish failed',
                payload={'response': body},
            )
        external_id = _extract_id(body)
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_id,
            external_status='published',
            message='Job published successfully',
            payload={'response': body},
        )

    def update(self, job: JobSnapshot, external_job_id: str, config: ProviderConfig) -> PublishResult:
        if not has_credentials(config):
            return credentials_missing_publish(self.provider_type)
        ok, body, err, _ = self._request(
            config,
            'update',
            path_vars={'externalJobId': external_job_id},
            json_body=to_job_payload(job, self.provider_type),
        )
        if not ok:
            return PublishResult(
                success=False,
                provider=self.provider_type,
                external_job_id=external_job_id,
                error=err or 'Update failed',
                message='Update failed',
                payload={'response': body},
            )
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status='updated',
            message='Job updated successfully',
            payload={'response': body},
        )

    def close(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        if not has_credentials(config):
            return credentials_missing_publish(self.provider_type)
        ok, body, err, _ = self._request(
            config, 'close', path_vars={'externalJobId': external_job_id}, json_body={}
        )
        if not ok:
            return PublishResult(
                success=False,
                provider=self.provider_type,
                external_job_id=external_job_id,
                error=err or 'Close failed',
                message='Close failed',
                payload={'response': body},
            )
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status='closed',
            message='Job closed successfully',
            payload={'response': body},
        )

    def get_job_status(self, external_job_id: str, config: ProviderConfig) -> PublishResult:
        if not has_credentials(config):
            return credentials_missing_publish(self.provider_type)
        if not self._endpoints(config).get('status'):
            return PublishResult(
                success=False,
                provider=self.provider_type,
                external_job_id=external_job_id,
                error='Endpoint "status" is not configured',
                message='Not supported',
            )
        ok, body, err, _ = self._request(
            config, 'status', path_vars={'externalJobId': external_job_id}
        )
        if not ok:
            return PublishResult(
                success=False,
                provider=self.provider_type,
                external_job_id=external_job_id,
                error=err or 'Status lookup failed',
                payload={'response': body},
            )
        status = None
        if isinstance(body, dict):
            status = body.get('status') or body.get('externalStatus')
        return PublishResult(
            success=True,
            provider=self.provider_type,
            external_job_id=external_job_id,
            external_status=str(status) if status is not None else None,
            payload={'response': body},
        )

    def reconcile_job(self, job: JobSnapshot, config: ProviderConfig) -> PublishResult:
        return PublishResult(
            success=False,
            provider=self.provider_type,
            error=(
                'Generic HTTP has no documented lookup-by-reference. '
                'A lost CREATE response can duplicate on retry (at-least-once).'
            ),
            message='Not supported',
        )

    def sync_applications(self, config: ProviderConfig) -> SyncResult:
        if not has_credentials(config):
            return SyncResult(
                success=False,
                provider=self.provider_type,
                error='Credentials required to sync applications',
                message='Credentials required',
            )
        # Prefer syncing per known external jobs — caller may pass job via settings temp key
        settings = self._settings(config)
        external_job_id = settings.get('_syncExternalJobId') or settings.get('externalJobId')
        path_vars = {'externalJobId': external_job_id} if external_job_id else {}
        ok, body, err, _ = self._request(config, 'applications', path_vars=path_vars or None)
        if not ok:
            return SyncResult(
                success=False,
                provider=self.provider_type,
                error=err or 'Sync failed',
                message='Sync failed',
            )
        apps = normalize_applications(body)
        # Stash normalized list on result message for manager persistence
        return SyncResult(
            success=True,
            provider=self.provider_type,
            imported_count=len(apps),
            message=f'Sync completed — {len(apps)} application(s)',
        )

    def sync_applications_detailed(
        self, config: ProviderConfig, *, external_job_id: str | None = None
    ) -> tuple[SyncResult, list[dict[str, Any]]]:
        """Like sync_applications but also returns normalized application rows."""
        if not has_credentials(config):
            return (
                SyncResult(
                    success=False,
                    provider=self.provider_type,
                    error='Credentials required to sync applications',
                    message='Credentials required',
                ),
                [],
            )
        settings = dict(self._settings(config))
        if external_job_id:
            settings['_syncExternalJobId'] = external_job_id
            # Temporarily override for this call
            config = ProviderConfig(
                id=config.id,
                company_key=config.company_key,
                company=config.company,
                provider=config.provider,
                enabled=config.enabled,
                status=config.status,
                auth_type=config.auth_type,
                auto_publish=config.auto_publish,
                auto_sync=config.auto_sync,
                client_id=config.client_id,
                client_secret=config.client_secret,
                access_token=config.access_token,
                refresh_token=config.refresh_token,
                expires_at=config.expires_at,
                settings=settings,
            )
        path_vars = {'externalJobId': external_job_id} if external_job_id else {}
        ok, body, err, _ = self._request(config, 'applications', path_vars=path_vars or None)
        if not ok:
            return (
                SyncResult(
                    success=False,
                    provider=self.provider_type,
                    error=err or 'Sync failed',
                    message='Sync failed',
                ),
                [],
            )
        apps = normalize_applications(body)
        return (
            SyncResult(
                success=True,
                provider=self.provider_type,
                imported_count=len(apps),
                message=f'Sync completed — {len(apps)} application(s)',
            ),
            apps,
        )

    def test_connection(self, config: ProviderConfig) -> ConnectionResult:
        if not has_credentials(config):
            return credentials_missing_connection(self.provider_type)
        if not self._base_url(config):
            return ConnectionResult(
                success=False,
                provider=self.provider_type,
                error='API Base URL is required',
                message='API Base URL is required',
            )
        ok, body, err, status = self._request(config, 'test')
        if not ok:
            return ConnectionResult(
                success=False,
                provider=self.provider_type,
                error=err or 'Connection failed',
                message='Connection failed',
            )
        return ConnectionResult(
            success=True,
            provider=self.provider_type,
            message='Connection verified',
        )


# Back-compat alias
GenericJobProvider = GenericHttpProvider
