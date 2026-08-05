"""Integration persistence (raw SQL via db_* helpers)."""
from __future__ import annotations

import json
from typing import Any

from app.database.connection.db import db_all, db_get, db_run


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _parse_settings(row: dict | None) -> dict:
    if not row:
        return {}
    raw = row.get('settings_json')
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw) or {}
        except json.JSONDecodeError:
            return {}
    return {}


# ---------------------------------------------------------------------------
# integration_provider
# ---------------------------------------------------------------------------

def get_provider_row(company_key: str, provider: str) -> dict | None:
    return db_get(
        '''
        SELECT * FROM integration_provider
        WHERE company_key = ? AND provider = ?
        ''',
        (company_key, provider),
    )


def get_provider_by_id(provider_id: int, company_key: str) -> dict | None:
    return db_get(
        '''
        SELECT * FROM integration_provider
        WHERE id = ? AND company_key = ?
        ''',
        (provider_id, company_key),
    )


def list_providers(company_key: str) -> list[dict]:
    return db_all(
        '''
        SELECT * FROM integration_provider
        WHERE company_key = ?
        ORDER BY provider ASC
        ''',
        (company_key,),
    )


def list_enabled_auto_publish(company_key: str) -> list[dict]:
    return db_all(
        '''
        SELECT * FROM integration_provider
        WHERE company_key = ? AND enabled = TRUE AND auto_publish = TRUE
        ORDER BY provider ASC
        ''',
        (company_key,),
    )


def list_enabled_providers(company_key: str) -> list[dict]:
    return db_all(
        '''
        SELECT * FROM integration_provider
        WHERE company_key = ? AND enabled = TRUE
        ORDER BY provider ASC
        ''',
        (company_key,),
    )


def upsert_provider(
    company_key: str,
    company: str | None,
    provider: str,
    *,
    enabled: bool | None = None,
    status: str | None = None,
    auth_type: str | None = None,
    auto_publish: bool | None = None,
    auto_sync: bool | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    access_token: str | None = None,
    refresh_token: str | None = None,
    expires_at: Any = None,
    settings_json: Any = None,
    update_secrets: bool = False,
) -> dict | None:
    existing = get_provider_row(company_key, provider)
    if not existing:
        result = db_run(
            '''
            INSERT INTO integration_provider (
                company_key, company, provider, enabled, status, auth_type,
                auto_publish, auto_sync, client_id, client_secret,
                access_token, refresh_token, expires_at, settings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb)
            RETURNING id
            ''',
            (
                company_key,
                company,
                provider,
                bool(enabled) if enabled is not None else False,
                status or 'disconnected',
                auth_type or 'api_key',
                bool(auto_publish) if auto_publish is not None else False,
                bool(auto_sync) if auto_sync is not None else False,
                client_id,
                client_secret,
                access_token,
                refresh_token,
                expires_at,
                _json_dumps(settings_json if settings_json is not None else {}),
            ),
        )
        return get_provider_by_id(result['lastID'], company_key) if result.get('lastID') else get_provider_row(company_key, provider)

    # Partial update
    enabled_v = existing['enabled'] if enabled is None else bool(enabled)
    status_v = existing['status'] if status is None else status
    auth_v = existing['auth_type'] if auth_type is None else auth_type
    auto_pub_v = existing['auto_publish'] if auto_publish is None else bool(auto_publish)
    auto_sync_v = existing['auto_sync'] if auto_sync is None else bool(auto_sync)
    client_id_v = existing['client_id'] if client_id is None else client_id
    settings_v = existing['settings_json'] if settings_json is None else settings_json
    expires_v = existing['expires_at'] if expires_at is None else expires_at
    company_v = company if company is not None else existing.get('company')

    if update_secrets:
        secret_v = client_secret if client_secret is not None else existing.get('client_secret')
        access_v = access_token if access_token is not None else existing.get('access_token')
        refresh_v = refresh_token if refresh_token is not None else existing.get('refresh_token')
    else:
        secret_v = existing.get('client_secret')
        access_v = existing.get('access_token')
        refresh_v = existing.get('refresh_token')
        if client_secret is not None and client_secret != '' and not str(client_secret).startswith('•'):
            secret_v = client_secret
        if access_token is not None and access_token != '' and not str(access_token).startswith('•'):
            access_v = access_token
        if refresh_token is not None and refresh_token != '' and not str(refresh_token).startswith('•'):
            refresh_v = refresh_token

    db_run(
        '''
        UPDATE integration_provider SET
            company = ?,
            enabled = ?,
            status = ?,
            auth_type = ?,
            auto_publish = ?,
            auto_sync = ?,
            client_id = ?,
            client_secret = ?,
            access_token = ?,
            refresh_token = ?,
            expires_at = ?,
            settings_json = ?::jsonb,
            updated_at = NOW()
        WHERE company_key = ? AND provider = ?
        ''',
        (
            company_v,
            enabled_v,
            status_v,
            auth_v,
            auto_pub_v,
            auto_sync_v,
            client_id_v,
            secret_v,
            access_v,
            refresh_v,
            expires_v,
            _json_dumps(settings_v if not isinstance(settings_v, str) else json.loads(settings_v) if settings_v else {}),
            company_key,
            provider,
        ),
    )
    return get_provider_row(company_key, provider)


def delete_provider(company_key: str, provider: str) -> int:
    result = db_run(
        'DELETE FROM integration_provider WHERE company_key = ? AND provider = ?',
        (company_key, provider),
    )
    return result.get('changes') or 0


def delete_provider_by_id(company_key: str, provider_id: int) -> int:
    result = db_run(
        'DELETE FROM integration_provider WHERE company_key = ? AND id = ?',
        (company_key, provider_id),
    )
    return result.get('changes') or 0


def row_to_settings(row: dict | None) -> dict:
    return _parse_settings(row)


# ---------------------------------------------------------------------------
# external_jobs
# ---------------------------------------------------------------------------

def get_external_job(job_id: str, provider: str) -> dict | None:
    return db_get(
        'SELECT * FROM external_jobs WHERE job_id = ? AND provider = ?',
        (job_id, provider),
    )


def get_external_job_by_id(external_row_id: int, company_key: str) -> dict | None:
    return db_get(
        'SELECT * FROM external_jobs WHERE id = ? AND company_key = ?',
        (external_row_id, company_key),
    )


def list_external_jobs(company_key: str, job_id: str | None = None) -> list[dict]:
    if job_id:
        return db_all(
            '''
            SELECT * FROM external_jobs
            WHERE company_key = ? AND job_id = ?
            ORDER BY provider ASC
            ''',
            (company_key, job_id),
        )
    return db_all(
        '''
        SELECT * FROM external_jobs
        WHERE company_key = ?
        ORDER BY updated_at DESC
        LIMIT 200
        ''',
        (company_key,),
    )


def upsert_external_job(
    company_key: str,
    job_id: str,
    provider: str,
    *,
    external_job_id: str | None = None,
    external_status: str | None = None,
    sync_status: str = 'pending',
    error_message: str | None = None,
    retry_count: int | None = None,
    request_payload: Any = None,
    response_payload: Any = None,
    mark_published: bool = False,
) -> dict | None:
    existing = get_external_job(job_id, provider)
    if not existing:
        db_run(
            '''
            INSERT INTO external_jobs (
                company_key, job_id, provider, external_job_id, external_status,
                published_at, last_sync, sync_status, error_message, retry_count,
                request_payload, response_payload
            ) VALUES (
                ?, ?, ?, ?, ?,
                CASE WHEN ? THEN NOW() ELSE NULL END,
                NOW(), ?, ?, ?,
                ?::jsonb, ?::jsonb
            )
            ''',
            (
                company_key,
                job_id,
                provider,
                external_job_id,
                external_status,
                mark_published,
                sync_status,
                error_message,
                retry_count or 0,
                _json_dumps(request_payload),
                _json_dumps(response_payload),
            ),
        )
        return get_external_job(job_id, provider)

    retry_v = existing.get('retry_count') or 0 if retry_count is None else retry_count
    db_run(
        '''
        UPDATE external_jobs SET
            external_job_id = COALESCE(?, external_job_id),
            external_status = COALESCE(?, external_status),
            sync_status = ?,
            error_message = ?,
            retry_count = ?,
            request_payload = COALESCE(?::jsonb, request_payload),
            response_payload = COALESCE(?::jsonb, response_payload),
            published_at = CASE WHEN ? AND published_at IS NULL THEN NOW() ELSE published_at END,
            last_sync = NOW(),
            updated_at = NOW()
        WHERE job_id = ? AND provider = ?
        ''',
        (
            external_job_id,
            external_status,
            sync_status,
            error_message,
            retry_v,
            _json_dumps(request_payload),
            _json_dumps(response_payload),
            mark_published,
            job_id,
            provider,
        ),
    )
    return get_external_job(job_id, provider)


def count_external_by_status(company_key: str) -> list[dict]:
    return db_all(
        '''
        SELECT provider, sync_status, COUNT(*)::int AS count
        FROM external_jobs
        WHERE company_key = ?
        GROUP BY provider, sync_status
        ''',
        (company_key,),
    )


# ---------------------------------------------------------------------------
# sync_logs
# ---------------------------------------------------------------------------

def insert_sync_log(
    company_key: str,
    provider: str,
    operation: str,
    status: str,
    *,
    job_id: str | None = None,
    external_job_id: str | None = None,
    request_payload: Any = None,
    response_payload: Any = None,
    execution_time_ms: int | None = None,
    retry_count: int = 0,
    error_message: str | None = None,
) -> int | None:
    result = db_run(
        '''
        INSERT INTO sync_logs (
            company_key, provider, operation, job_id, external_job_id,
            request_payload, response_payload, status, execution_time_ms,
            retry_count, error_message
        ) VALUES (?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, ?, ?, ?, ?)
        RETURNING id
        ''',
        (
            company_key,
            provider,
            operation,
            job_id,
            external_job_id,
            _json_dumps(request_payload),
            _json_dumps(response_payload),
            status,
            execution_time_ms,
            retry_count,
            error_message,
        ),
    )
    return result.get('lastID')


def list_sync_logs(company_key: str, limit: int = 50, provider: str | None = None) -> list[dict]:
    limit = max(1, min(int(limit or 50), 200))
    if provider:
        return db_all(
            '''
            SELECT * FROM sync_logs
            WHERE company_key = ? AND provider = ?
            ORDER BY created_at DESC
            LIMIT ?
            ''',
            (company_key, provider, limit),
        )
    return db_all(
        '''
        SELECT * FROM sync_logs
        WHERE company_key = ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (company_key, limit),
    )


# ---------------------------------------------------------------------------
# provider_events
# ---------------------------------------------------------------------------

def insert_provider_event(
    event_type: str,
    *,
    company_key: str | None = None,
    job_id: str | None = None,
    provider: str | None = None,
    payload: Any = None,
    status: str = 'pending',
) -> int | None:
    result = db_run(
        '''
        INSERT INTO provider_events (company_key, event_type, job_id, provider, payload, status)
        VALUES (?, ?, ?, ?, ?::jsonb, ?)
        RETURNING id
        ''',
        (company_key, event_type, job_id, provider, _json_dumps(payload), status),
    )
    return result.get('lastID')


def insert_webhook_event(
    provider: str,
    *,
    company_key: str | None = None,
    event_type: str | None = None,
    payload: Any = None,
    headers_json: Any = None,
) -> int | None:
    result = db_run(
        '''
        INSERT INTO webhook_events (company_key, provider, event_type, payload, headers_json)
        VALUES (?, ?, ?, ?::jsonb, ?::jsonb)
        RETURNING id
        ''',
        (company_key, provider, event_type, _json_dumps(payload), _json_dumps(headers_json)),
    )
    return result.get('lastID')
