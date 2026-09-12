"""Integration persistence (raw SQL via db_* helpers).

Tenant boundary: every lookup/scope filter below MUST use ``organization_id``
(the immutable tenant identity), never ``company_key`` (a lowercased/stripped
company *name*). Two unrelated organizations can share the same or a
similar-looking name and would therefore collide on ``company_key`` — see
BUG-004. ``company_key``/``company`` are still stored on rows for display and
backward-compatible reporting only.
"""
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

def get_provider_row(organization_id: str, provider: str) -> dict | None:
    return db_get(
        '''
        SELECT * FROM integration_provider
        WHERE organization_id = ? AND provider = ?
        ''',
        (organization_id, provider),
    )


def get_provider_by_id(provider_id: int, organization_id: str) -> dict | None:
    return db_get(
        '''
        SELECT * FROM integration_provider
        WHERE id = ? AND organization_id = ?
        ''',
        (provider_id, organization_id),
    )


def list_providers(organization_id: str) -> list[dict]:
    return db_all(
        '''
        SELECT * FROM integration_provider
        WHERE organization_id = ?
        ORDER BY provider ASC
        ''',
        (organization_id,),
    )


def list_enabled_auto_publish(organization_id: str) -> list[dict]:
    return db_all(
        '''
        SELECT * FROM integration_provider
        WHERE organization_id = ? AND enabled = TRUE AND auto_publish = TRUE
        ORDER BY provider ASC
        ''',
        (organization_id,),
    )


def list_enabled_providers(organization_id: str) -> list[dict]:
    return db_all(
        '''
        SELECT * FROM integration_provider
        WHERE organization_id = ? AND enabled = TRUE
        ORDER BY provider ASC
        ''',
        (organization_id,),
    )


def upsert_provider(
    organization_id: str,
    company: str | None,
    provider: str,
    *,
    company_key: str | None = None,
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
    existing = get_provider_row(organization_id, provider)
    if not existing:
        result = db_run(
            '''
            INSERT INTO integration_provider (
                organization_id, company_key, company, provider, enabled, status, auth_type,
                auto_publish, auto_sync, client_id, client_secret,
                access_token, refresh_token, expires_at, settings_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb)
            RETURNING id
            ''',
            (
                organization_id,
                company_key or '',
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
        return get_provider_by_id(result['lastID'], organization_id) if result.get('lastID') else get_provider_row(organization_id, provider)

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
    company_key_v = company_key if company_key is not None else existing.get('company_key')

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
            company_key = ?,
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
        WHERE organization_id = ? AND provider = ?
        ''',
        (
            company_v,
            company_key_v,
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
            organization_id,
            provider,
        ),
    )
    return get_provider_row(organization_id, provider)


def delete_provider(organization_id: str, provider: str) -> int:
    result = db_run(
        'DELETE FROM integration_provider WHERE organization_id = ? AND provider = ?',
        (organization_id, provider),
    )
    return result.get('changes') or 0


def delete_provider_by_id(organization_id: str, provider_id: int) -> int:
    result = db_run(
        'DELETE FROM integration_provider WHERE organization_id = ? AND id = ?',
        (organization_id, provider_id),
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


def get_external_job_by_id(external_row_id: int, organization_id: str) -> dict | None:
    return db_get(
        'SELECT * FROM external_jobs WHERE id = ? AND organization_id = ?',
        (external_row_id, organization_id),
    )


def list_external_jobs(organization_id: str, job_id: str | None = None) -> list[dict]:
    if job_id:
        return db_all(
            '''
            SELECT * FROM external_jobs
            WHERE organization_id = ? AND job_id = ?
            ORDER BY provider ASC
            ''',
            (organization_id, job_id),
        )
    return db_all(
        '''
        SELECT * FROM external_jobs
        WHERE organization_id = ?
        ORDER BY updated_at DESC
        LIMIT 200
        ''',
        (organization_id,),
    )


def upsert_external_job(
    organization_id: str,
    job_id: str,
    provider: str,
    *,
    company_key: str | None = None,
    external_job_id: str | None = None,
    external_status: str | None = None,
    sync_status: str = 'pending',
    error_message: str | None = None,
    retry_count: int | None = None,
    request_payload: Any = None,
    response_payload: Any = None,
    mark_published: bool = False,
    pending_operation: str | None = None,
    next_attempt_at: Any = None,
    clear_lease: bool | None = None,
    due_now: bool = False,
) -> dict | None:
    existing = get_external_job(job_id, provider)
    # Leaving pending (or explicit clear) drops the worker lease so reclaim is clean.
    if clear_lease is None:
        clear_lease = sync_status != 'pending'
    if due_now:
        next_attempt_at = None
    if not existing:
        db_run(
            '''
            INSERT INTO external_jobs (
                organization_id, company_key, job_id, provider, external_job_id, external_status,
                published_at, last_sync, sync_status, error_message, retry_count,
                request_payload, response_payload,
                pending_operation, next_attempt_at,
                leased_by, leased_until
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                CASE WHEN ? THEN NOW() ELSE NULL END,
                NOW(), ?, ?, ?,
                ?::jsonb, ?::jsonb,
                ?,
                CASE WHEN ? THEN NOW() ELSE COALESCE(?, NOW()) END,
                NULL, NULL
            )
            ''',
            (
                organization_id,
                company_key or '',
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
                pending_operation if sync_status == 'pending' else None,
                due_now or (sync_status == 'pending' and next_attempt_at is None),
                next_attempt_at,
            ),
        )
        return get_external_job(job_id, provider)

    retry_v = existing.get('retry_count') or 0 if retry_count is None else retry_count
    op_v = pending_operation
    if sync_status == 'pending' and op_v is None:
        op_v = existing.get('pending_operation') or 'publish'
    if sync_status != 'pending':
        op_v = None

    force_now = bool(due_now) or (
        sync_status == 'pending' and next_attempt_at is None and pending_operation is not None
    )
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
            updated_at = NOW(),
            pending_operation = ?,
            next_attempt_at = CASE
                WHEN ? THEN NOW()
                WHEN ?::timestamptz IS NOT NULL THEN ?::timestamptz
                WHEN ? = 'pending' THEN COALESCE(next_attempt_at, NOW())
                ELSE NULL
            END,
            leased_by = CASE WHEN ? THEN NULL ELSE leased_by END,
            leased_until = CASE WHEN ? THEN NULL ELSE leased_until END
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
            op_v,
            force_now,
            next_attempt_at,
            next_attempt_at,
            sync_status,
            clear_lease,
            clear_lease,
            job_id,
            provider,
        ),
    )
    return get_external_job(job_id, provider)


DEFAULT_OUTBOX_LEASE_SECONDS = 120


def _lease_until(lease_seconds: int):
    from datetime import datetime, timedelta, timezone

    return datetime.now(timezone.utc) + timedelta(seconds=max(30, int(lease_seconds)))


def claim_pending_external_jobs(
    worker_id: str,
    *,
    limit: int = 10,
    lease_seconds: int = DEFAULT_OUTBOX_LEASE_SECONDS,
    job_id: str | None = None,
) -> list[dict]:
    """
    Atomically claim pending outbox rows (SKIP LOCKED).

    Two workers never receive the same row. Expired leases are reclaimable.
    """
    from app.database.connection.db import get_conn
    from psycopg.rows import dict_row

    until = _lease_until(lease_seconds)
    lim = max(1, min(int(limit), 200))
    params: list = []
    job_filter = ''
    if job_id:
        job_filter = 'AND job_id = %s'
        params.append(job_id)
    params.extend([lim, worker_id, until])
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f'''
                WITH cte AS (
                    SELECT id
                    FROM external_jobs
                    WHERE sync_status = 'pending'
                      AND COALESCE(next_attempt_at, TIMESTAMPTZ '-infinity') <= NOW()
                      AND (leased_until IS NULL OR leased_until < NOW())
                      {job_filter}
                    ORDER BY COALESCE(next_attempt_at, created_at) ASC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                )
                UPDATE external_jobs e
                SET leased_by = %s,
                    leased_until = %s,
                    updated_at = NOW()
                FROM cte
                WHERE e.id = cte.id
                RETURNING e.*
                ''',
                tuple(params),
            )
            rows = cur.fetchall() or []
            return [dict(r) for r in rows]


def release_external_job_lease(external_row_id: int) -> None:
    db_run(
        '''
        UPDATE external_jobs
        SET leased_by = NULL, leased_until = NULL, updated_at = NOW()
        WHERE id = ?
        ''',
        (external_row_id,),
    )


def release_leases_for_worker(worker_id: str) -> int:
    result = db_run(
        '''
        UPDATE external_jobs
        SET leased_by = NULL, leased_until = NULL, updated_at = NOW()
        WHERE leased_by = ?
        ''',
        (worker_id,),
    )
    return int((result or {}).get('changes') or 0)


def schedule_external_job_retry(
    organization_id: str,
    job_id: str,
    provider: str,
    *,
    pending_operation: str,
    retry_count: int,
    error_message: str | None,
    next_attempt_at,
) -> None:
    upsert_external_job(
        organization_id,
        job_id,
        provider,
        sync_status='pending',
        error_message=error_message,
        retry_count=retry_count,
        pending_operation=pending_operation,
        next_attempt_at=next_attempt_at,
        clear_lease=True,
    )


def recover_external_job_id_from_logs(job_id: str, provider: str) -> str | None:
    """
    If publish succeeded externally but the process died before persisting
    external_job_id, recover it from sync_logs to avoid duplicate creates.
    """
    row = db_get(
        '''
        SELECT external_job_id, response_payload
        FROM sync_logs
        WHERE job_id = ?
          AND provider = ?
          AND operation IN ('publish', 'update')
          AND status = 'success'
          AND (
            external_job_id IS NOT NULL
            OR response_payload IS NOT NULL
          )
        ORDER BY created_at DESC
        LIMIT 1
        ''',
        (job_id, provider),
    )
    if not row:
        return None
    eid = (row.get('external_job_id') or '').strip()
    if eid:
        return eid
    payload = row.get('response_payload')
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = None
    if isinstance(payload, dict):
        for key in ('external_job_id', 'externalJobId', 'id', 'jobId'):
            val = payload.get(key)
            if val:
                return str(val)
    return None


def count_external_by_status(organization_id: str) -> list[dict]:
    return db_all(
        '''
        SELECT provider, sync_status, COUNT(*)::int AS count
        FROM external_jobs
        WHERE organization_id = ?
        GROUP BY provider, sync_status
        ''',
        (organization_id,),
    )


# ---------------------------------------------------------------------------
# sync_logs
# ---------------------------------------------------------------------------

def insert_sync_log(
    organization_id: str | None,
    provider: str,
    operation: str,
    status: str,
    *,
    company_key: str | None = None,
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
            organization_id, company_key, provider, operation, job_id, external_job_id,
            request_payload, response_payload, status, execution_time_ms,
            retry_count, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, ?, ?, ?, ?)
        RETURNING id
        ''',
        (
            organization_id,
            company_key or 'unknown',
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


def list_sync_logs(organization_id: str, limit: int = 50, provider: str | None = None) -> list[dict]:
    limit = max(1, min(int(limit or 50), 200))
    if provider:
        return db_all(
            '''
            SELECT * FROM sync_logs
            WHERE organization_id = ? AND provider = ?
            ORDER BY created_at DESC
            LIMIT ?
            ''',
            (organization_id, provider, limit),
        )
    return db_all(
        '''
        SELECT * FROM sync_logs
        WHERE organization_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        ''',
        (organization_id, limit),
    )


# ---------------------------------------------------------------------------
# provider_events
# ---------------------------------------------------------------------------

def insert_provider_event(
    event_type: str,
    *,
    organization_id: str | None = None,
    company_key: str | None = None,
    job_id: str | None = None,
    provider: str | None = None,
    payload: Any = None,
    status: str = 'pending',
) -> int | None:
    """Persist domain events into sync_logs (provider_events table removed)."""
    return insert_sync_log(
        organization_id,
        provider or 'system',
        event_type or 'provider_event',
        status=status or 'dispatched',
        company_key=company_key,
        job_id=job_id,
        request_payload=payload,
    )


def insert_webhook_event(
    provider: str,
    *,
    organization_id: str | None = None,
    company_key: str | None = None,
    event_type: str | None = None,
    payload: Any = None,
    headers_json: Any = None,
) -> int | None:
    """Persist webhooks into sync_logs (webhook_events table removed)."""
    return insert_sync_log(
        organization_id,
        provider,
        event_type or 'webhook',
        status='pending',
        company_key=company_key,
        request_payload=payload,
        response_payload=headers_json,
    )


# ---------------------------------------------------------------------------
# external_applications
# ---------------------------------------------------------------------------

def upsert_external_application(
    organization_id: str,
    provider: str,
    external_application_id: str,
    *,
    company_key: str | None = None,
    job_id: str | None = None,
    external_job_id: str | None = None,
    candidate_email: str | None = None,
    candidate_name: str | None = None,
    mapped_status: str | None = None,
    payload: Any = None,
) -> None:
    existing = db_get(
        '''
        SELECT id FROM external_applications
        WHERE organization_id = ? AND provider = ? AND external_application_id = ?
        ''',
        (organization_id, provider, external_application_id),
    )
    if existing:
        db_run(
            '''
            UPDATE external_applications SET
                job_id = COALESCE(?, job_id),
                external_job_id = COALESCE(?, external_job_id),
                candidate_email = COALESCE(?, candidate_email),
                candidate_name = COALESCE(?, candidate_name),
                mapped_status = COALESCE(?, mapped_status),
                payload = COALESCE(?::jsonb, payload),
                last_synced_at = NOW(),
                updated_at = NOW()
            WHERE id = ?
            ''',
            (
                job_id,
                external_job_id,
                candidate_email,
                candidate_name,
                mapped_status,
                _json_dumps(payload),
                existing['id'],
            ),
        )
        return
    db_run(
        '''
        INSERT INTO external_applications (
            organization_id, company_key, provider, job_id, external_job_id, external_application_id,
            candidate_email, candidate_name, mapped_status, payload
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb)
        ''',
        (
            organization_id,
            company_key or '',
            provider,
            job_id,
            external_job_id,
            external_application_id,
            candidate_email,
            candidate_name,
            mapped_status,
            _json_dumps(payload),
        ),
    )


def list_external_applications(
    organization_id: str,
    *,
    provider: str | None = None,
    job_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    limit = max(1, min(int(limit or 100), 500))
    if provider and job_id:
        return db_all(
            '''
            SELECT * FROM external_applications
            WHERE organization_id = ? AND provider = ? AND job_id = ?
            ORDER BY last_synced_at DESC LIMIT ?
            ''',
            (organization_id, provider, job_id, limit),
        )
    if provider:
        return db_all(
            '''
            SELECT * FROM external_applications
            WHERE organization_id = ? AND provider = ?
            ORDER BY last_synced_at DESC LIMIT ?
            ''',
            (organization_id, provider, limit),
        )
    return db_all(
        '''
        SELECT * FROM external_applications
        WHERE organization_id = ?
        ORDER BY last_synced_at DESC LIMIT ?
        ''',
        (organization_id, limit),
    )


def list_auto_sync_http_providers() -> list[dict]:
    """All company providers with auto_sync enabled (filter adapter in service)."""
    return db_all(
        '''
        SELECT * FROM integration_provider
        WHERE enabled = TRUE AND auto_sync = TRUE
        ORDER BY organization_id, provider
        '''
    )
