"""Integrations REST API — /api/integrations

Every route resolves ``organization_id`` server-side (JWT/DB, never a client-
supplied value) and uses it as the sole tenant-scoping key for every
persistence call. ``company_key``/``company`` are display metadata only —
see BUG-004.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from app.api.middleware.auth import authenticate_token, require_head_hr, require_recruiter
from app.domains.identity.authorization.rbac import (
    get_role,
    has_permission,
    is_read_only,
    same_organization,
    _resolve_job_organization_id,
)
from app.domains.integrations.company_context import resolve_organization_for_user
from app.domains.integrations.config import is_builtin, is_valid_provider_slug, slugify_provider
from app.domains.integrations import repository as repo
from app.domains.integrations.service import provider_config as config_svc
from app.domains.integrations.service.dashboard_service import build_dashboard, build_status
from app.domains.integrations.service.manager import IntegrationManagerService
from app.domains.integrations.service import publish_service
from app.domains.integrations.service.serializers import serialize_external_job, serialize_log_row
from app.database.connection.db import db_get

logger = logging.getLogger(__name__)

integrations_bp = Blueprint('integrations', __name__)
_manager = IntegrationManagerService()


def _org_or_403(user):
    """Resolve the caller's organization_id server-side. Never trust a client value."""
    org_id, display = resolve_organization_for_user(user)
    if not org_id:
        return None, None, (jsonify({'error': 'Company context required'}), 403)
    return org_id, display, None


def _can_configure(user) -> bool:
    return has_permission(user, 'settings:configure') or get_role(user) == 'HEAD_HR'


def _can_publish(user) -> bool:
    return get_role(user) in ('RECRUITER', 'HEAD_HR') and not is_read_only(user)


def _job_belongs_to_org(job_id: str, organization_id: str, user) -> bool:
    """Authorize job access by organization_id. Deny when org cannot be resolved."""
    job = db_get('SELECT * FROM jobs WHERE jdid = ?', (job_id,))
    if not job:
        return False
    org_id = job.get('organization_id')
    if org_id:
        return str(org_id) == str(organization_id) and same_organization(user, org_id)
    owner_org = _resolve_job_organization_id(
        organization_id=None,
        posted_by=job.get('posted_by'),
    )
    if owner_org:
        return str(owner_org) == str(organization_id) and same_organization(user, owner_org)
    return False


def _provider_known(organization_id: str, provider: str) -> bool:
    if is_builtin(provider):
        return True
    return bool(repo.get_provider_row(organization_id, provider))


@integrations_bp.get('/')
@authenticate_token
def integrations_root():
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    return jsonify({
        'status': 'ok',
        'providers': config_svc.catalog_with_status(organization_id),
        'summary': build_status(organization_id),
    })


@integrations_bp.get('/providers')
@authenticate_token
def list_providers():
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    return jsonify({'providers': config_svc.catalog_with_status(organization_id)})


@integrations_bp.get('/provider/<string:provider>')
@authenticate_token
def get_provider(provider: str):
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if not _provider_known(organization_id, provider):
        return jsonify({'error': 'Unknown provider'}), 404
    cfg = config_svc.get_provider_config(organization_id, provider)
    return jsonify({'provider': cfg})


@integrations_bp.post('/provider')
@require_head_hr
def create_or_upsert_provider():
    organization_id, company, err = _org_or_403(request.user)
    if err:
        return err
    data = request.get_json(force=True) or {}
    provider = (data.get('provider') or '').strip().lower()
    if not provider:
        name = (data.get('name') or data.get('displayName') or '').strip()
        provider = slugify_provider(name)
        data['provider'] = provider
        if name and not data.get('displayName'):
            data['displayName'] = name
    if not provider:
        return jsonify({'error': 'provider or name is required'}), 400
    # Custom platforms must not overwrite reserved builtin ids via "create custom"
    if data.get('custom') or data.get('settings') or data.get('baseUrl') or data.get('endpoints'):
        if is_builtin(provider) and data.get('custom'):
            return jsonify({'error': f'{provider} is a built-in platform; configure it without custom=true'}), 400
    try:
        cfg = config_svc.save_provider_config(organization_id, company, provider, data)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'provider': cfg}), 201


@integrations_bp.put('/provider/<string:provider>')
@require_head_hr
def update_provider(provider: str):
    organization_id, company, err = _org_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if not is_valid_provider_slug(provider):
        return jsonify({'error': 'Invalid provider'}), 400
    if not is_builtin(provider) and not repo.get_provider_row(organization_id, provider):
        # Allow PUT to create custom if body includes baseUrl
        data = request.get_json(force=True) or {}
        if not (data.get('baseUrl') or (data.get('settings') or {}).get('baseUrl')):
            return jsonify({'error': 'Unknown provider'}), 404
    data = request.get_json(force=True) or {}
    data['provider'] = provider
    try:
        cfg = config_svc.save_provider_config(organization_id, company, provider, data)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'provider': cfg})


@integrations_bp.delete('/provider/<string:provider_or_id>')
@require_head_hr
def delete_provider(provider_or_id: str):
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    # Prefer deleting custom platforms; builtins can clear config too
    ok = config_svc.delete_provider_config(organization_id, provider_or_id)
    if not ok:
        return jsonify({'error': 'Provider configuration not found'}), 404
    return jsonify({'message': 'Provider configuration deleted'})


@integrations_bp.post('/provider/<string:provider>/connect')
@require_head_hr
def connect_provider(provider: str):
    organization_id, company, err = _org_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if not _provider_known(organization_id, provider) and not is_builtin(provider):
        return jsonify({'error': 'Unknown provider'}), 404
    data = request.get_json(force=True) or {}
    data['status'] = 'connected'
    try:
        cfg = config_svc.save_provider_config(organization_id, company, provider, data, connect=True)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'provider': cfg, 'message': 'Provider connected'})


@integrations_bp.post('/provider/<string:provider>/disconnect')
@require_head_hr
def disconnect_provider(provider: str):
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if not _provider_known(organization_id, provider):
        return jsonify({'error': 'Unknown provider'}), 404
    cfg = config_svc.disconnect_provider(organization_id, provider)
    return jsonify({'provider': cfg, 'message': 'Provider disconnected'})


@integrations_bp.post('/provider/<string:provider>/test')
@authenticate_token
def test_provider(provider: str):
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    if not (_can_configure(request.user) or _can_publish(request.user)):
        return jsonify({'error': 'Forbidden'}), 403
    provider = provider.strip().lower()
    if not _provider_known(organization_id, provider) and not is_builtin(provider):
        return jsonify({'error': 'Unknown provider'}), 404
    result = _manager.test_connection(organization_id, provider)
    status = 200 if result.success else 400
    return jsonify({'result': result.to_dict()}), status


@integrations_bp.post('/provider/<string:provider>/sync')
@require_recruiter
def sync_provider(provider: str):
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if not _provider_known(organization_id, provider):
        return jsonify({'error': 'Unknown provider'}), 404
    result = _manager.sync_provider(organization_id, provider)
    status = 200 if result.success else 400
    return jsonify({'result': result.to_dict()}), status


@integrations_bp.post('/publish/<string:job_id>')
@require_recruiter
def publish_job(job_id: str):
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    if not _job_belongs_to_org(job_id, organization_id, request.user):
        return jsonify({'error': 'Job not found'}), 404
    data = request.get_json(silent=True) or {}
    providers = data.get('providers')
    if providers is not None and not isinstance(providers, list):
        return jsonify({'error': 'providers must be a list'}), 400
    result = publish_service.enqueue_publish(
        organization_id,
        job_id,
        providers=providers,
        auto_publish_only=False,
        operation='publish',
    )
    return jsonify(result), 202


@integrations_bp.post('/republish/<string:job_id>')
@require_recruiter
def republish_job(job_id: str):
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    if not _job_belongs_to_org(job_id, organization_id, request.user):
        return jsonify({'error': 'Job not found'}), 404
    data = request.get_json(silent=True) or {}
    providers = data.get('providers')
    result = publish_service.enqueue_publish(
        organization_id,
        job_id,
        providers=providers,
        auto_publish_only=False,
        operation='republish',
    )
    return jsonify(result), 202


@integrations_bp.post('/retry/<int:external_job_id>')
@require_recruiter
def retry_external_job(external_job_id: int):
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    result = publish_service.enqueue_retry(organization_id, external_job_id)
    if not result:
        return jsonify({'error': 'External job not found'}), 404
    return jsonify(result), 202


@integrations_bp.get('/jobs')
@authenticate_token
def list_external_jobs():
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    job_id = request.args.get('jobId') or request.args.get('job_id')
    rows = repo.list_external_jobs(organization_id, job_id=job_id)
    return jsonify({'jobs': [serialize_external_job(r) for r in rows]})


@integrations_bp.get('/applications')
@authenticate_token
def list_external_applications():
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    provider = request.args.get('provider')
    job_id = request.args.get('jobId') or request.args.get('job_id')
    try:
        limit = int(request.args.get('limit', 100))
    except ValueError:
        limit = 100
    rows = repo.list_external_applications(
        organization_id, provider=provider, job_id=job_id, limit=limit
    )
    apps = []
    for r in rows:
        apps.append({
            'id': r.get('id'),
            'organizationId': str(r.get('organization_id')) if r.get('organization_id') else None,
            'companyKey': r.get('company_key'),
            'provider': r.get('provider'),
            'jobId': r.get('job_id'),
            'externalJobId': r.get('external_job_id'),
            'externalApplicationId': r.get('external_application_id'),
            'candidateEmail': r.get('candidate_email'),
            'candidateName': r.get('candidate_name'),
            'status': r.get('mapped_status'),
            'lastSyncedAt': r.get('last_synced_at').isoformat()
            if getattr(r.get('last_synced_at'), 'isoformat', None)
            else r.get('last_synced_at'),
            'payload': r.get('payload'),
        })
    return jsonify({'applications': apps})


@integrations_bp.get('/logs')
@authenticate_token
def list_logs():
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    limit = request.args.get('limit', 50)
    provider = request.args.get('provider')
    try:
        limit_i = int(limit)
    except ValueError:
        limit_i = 50
    rows = repo.list_sync_logs(organization_id, limit=limit_i, provider=provider)
    return jsonify({'logs': [serialize_log_row(r) for r in rows]})


@integrations_bp.get('/status')
@authenticate_token
def integration_status():
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    return jsonify(build_status(organization_id))


@integrations_bp.get('/dashboard')
@authenticate_token
def integration_dashboard():
    organization_id, _, err = _org_or_403(request.user)
    if err:
        return err
    return jsonify(build_dashboard(organization_id))
