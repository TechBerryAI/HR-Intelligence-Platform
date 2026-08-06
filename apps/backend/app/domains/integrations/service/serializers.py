"""Map DB provider rows ↔ ProviderConfig (with decrypt for runtime use)."""
from __future__ import annotations

import json

from app.domains.integrations.dto import ProviderConfig
from app.domains.integrations.repository import row_to_settings
from app.domains.integrations.security.secrets import decrypt_secret


def row_to_provider_config(row: dict | None, *, decrypt: bool = True) -> ProviderConfig | None:
    if not row:
        return None
    settings = row_to_settings(row)
    secret = row.get('client_secret')
    access = row.get('access_token')
    refresh = row.get('refresh_token')
    if decrypt:
        secret = decrypt_secret(secret)
        access = decrypt_secret(access)
        refresh = decrypt_secret(refresh)
    return ProviderConfig(
        id=row.get('id'),
        company_key=row.get('company_key') or '',
        company=row.get('company'),
        provider=row.get('provider') or '',
        enabled=bool(row.get('enabled')),
        status=row.get('status') or 'disconnected',
        auth_type=row.get('auth_type') or 'api_key',
        auto_publish=bool(row.get('auto_publish')),
        auto_sync=bool(row.get('auto_sync')),
        client_id=row.get('client_id'),
        client_secret=secret,
        access_token=access,
        refresh_token=refresh,
        expires_at=row.get('expires_at'),
        settings=settings if isinstance(settings, dict) else {},
    )


def serialize_log_row(row: dict) -> dict:
    def _j(v):
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v

    return {
        'id': row.get('id'),
        'companyKey': row.get('company_key'),
        'provider': row.get('provider'),
        'operation': row.get('operation'),
        'jobId': row.get('job_id'),
        'externalJobId': row.get('external_job_id'),
        'requestPayload': _j(row.get('request_payload')),
        'responsePayload': _j(row.get('response_payload')),
        'status': row.get('status'),
        'executionTimeMs': row.get('execution_time_ms'),
        'retryCount': row.get('retry_count'),
        'errorMessage': row.get('error_message'),
        'createdAt': row.get('created_at').isoformat() if getattr(row.get('created_at'), 'isoformat', None) else row.get('created_at'),
    }


def serialize_external_job(row: dict) -> dict:
    return {
        'id': row.get('id'),
        'companyKey': row.get('company_key'),
        'jobId': row.get('job_id'),
        'provider': row.get('provider'),
        'externalJobId': row.get('external_job_id'),
        'externalStatus': row.get('external_status'),
        'publishedAt': row.get('published_at').isoformat() if getattr(row.get('published_at'), 'isoformat', None) else row.get('published_at'),
        'lastSync': row.get('last_sync').isoformat() if getattr(row.get('last_sync'), 'isoformat', None) else row.get('last_sync'),
        'syncStatus': row.get('sync_status'),
        'errorMessage': row.get('error_message'),
        'retryCount': row.get('retry_count') or 0,
    }
