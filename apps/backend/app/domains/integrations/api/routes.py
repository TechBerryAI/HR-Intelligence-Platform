"""Integrations REST API — /api/integrations"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from app.api.middleware.auth import authenticate_token, require_head_hr, require_recruiter
from app.domains.identity.authorization.rbac import get_role, has_permission, is_read_only
from app.domains.integrations.company_context import resolve_company_for_user
from app.domains.integrations.config import VALID_PROVIDERS
from app.domains.integrations import repository as repo
from app.domains.integrations.service import provider_config as config_svc
from app.domains.integrations.service.dashboard_service import build_dashboard, build_status
from app.domains.integrations.service.manager import IntegrationManagerService
from app.domains.integrations.service import publish_service
from app.domains.integrations.service.serializers import serialize_external_job, serialize_log_row
from app.domains.recruitment.services.company_scope import companies_related, normalize_company
from app.database.connection.db import db_get

logger = logging.getLogger(__name__)

integrations_bp = Blueprint('integrations', __name__)
_manager = IntegrationManagerService()


def _company_or_403(user):
    key, display = resolve_company_for_user(user)
    if not key:
        return None, None, (jsonify({'error': 'Company context required'}), 403)
    return key, display, None


def _can_configure(user) -> bool:
    return has_permission(user, 'settings:configure') or get_role(user) == 'HEAD_HR'


def _can_publish(user) -> bool:
    return get_role(user) in ('RECRUITER', 'HEAD_HR') and not is_read_only(user)


def _job_belongs_to_company(job_id: str, company_key: str, user) -> bool:
    job = db_get('SELECT * FROM jobs WHERE jdid = ?', (job_id,))
    if not job:
        return False
    job_key = normalize_company(job.get('company') or '')
    if job_key and job_key == company_key:
        return True
    # Fallback: companies_related against user company
    _, display = resolve_company_for_user(user)
    return companies_related(display, job.get('company'))


@integrations_bp.get('/')
@authenticate_token
def integrations_root():
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    return jsonify({
        'status': 'ok',
        'providers': config_svc.catalog_with_status(company_key),
        'summary': build_status(company_key),
    })


@integrations_bp.get('/providers')
@authenticate_token
def list_providers():
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    return jsonify({'providers': config_svc.catalog_with_status(company_key)})


@integrations_bp.get('/provider/<string:provider>')
@authenticate_token
def get_provider(provider: str):
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if provider not in VALID_PROVIDERS:
        return jsonify({'error': 'Unknown provider'}), 404
    cfg = config_svc.get_provider_config(company_key, provider)
    return jsonify({'provider': cfg})


@integrations_bp.post('/provider')
@require_head_hr
def create_or_upsert_provider():
    company_key, company, err = _company_or_403(request.user)
    if err:
        return err
    data = request.get_json(force=True) or {}
    provider = (data.get('provider') or '').strip().lower()
    if not provider:
        return jsonify({'error': 'provider is required'}), 400
    try:
        cfg = config_svc.save_provider_config(company_key, company, provider, data)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'provider': cfg}), 201


@integrations_bp.put('/provider/<string:provider>')
@require_head_hr
def update_provider(provider: str):
    company_key, company, err = _company_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if provider not in VALID_PROVIDERS:
        return jsonify({'error': 'Unknown provider'}), 404
    data = request.get_json(force=True) or {}
    data['provider'] = provider
    try:
        cfg = config_svc.save_provider_config(company_key, company, provider, data)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'provider': cfg})


@integrations_bp.delete('/provider/<string:provider_or_id>')
@require_head_hr
def delete_provider(provider_or_id: str):
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    ok = config_svc.delete_provider_config(company_key, provider_or_id)
    if not ok:
        return jsonify({'error': 'Provider configuration not found'}), 404
    return jsonify({'message': 'Provider configuration deleted'})


@integrations_bp.post('/provider/<string:provider>/connect')
@require_head_hr
def connect_provider(provider: str):
    company_key, company, err = _company_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if provider not in VALID_PROVIDERS:
        return jsonify({'error': 'Unknown provider'}), 404
    data = request.get_json(force=True) or {}
    data['status'] = 'connected'
    cfg = config_svc.save_provider_config(company_key, company, provider, data, connect=True)
    return jsonify({'provider': cfg, 'message': 'Provider connected'})


@integrations_bp.post('/provider/<string:provider>/disconnect')
@require_head_hr
def disconnect_provider(provider: str):
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    provider = provider.strip().lower()
    if provider not in VALID_PROVIDERS:
        return jsonify({'error': 'Unknown provider'}), 404
    cfg = config_svc.disconnect_provider(company_key, provider)
    return jsonify({'provider': cfg, 'message': 'Provider disconnected'})


@integrations_bp.post('/provider/<string:provider>/test')
@authenticate_token
def test_provider(provider: str):
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    if not (_can_configure(request.user) or _can_publish(request.user)):
        return jsonify({'error': 'Forbidden'}), 403
    provider = provider.strip().lower()
    if provider not in VALID_PROVIDERS:
        return jsonify({'error': 'Unknown provider'}), 404
    result = _manager.test_connection(company_key, provider)
    status = 200 if result.success else 400
    return jsonify({'result': result.to_dict()}), status


@integrations_bp.post('/publish/<string:job_id>')
@require_recruiter
def publish_job(job_id: str):
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    if not _job_belongs_to_company(job_id, company_key, request.user):
        return jsonify({'error': 'Job not found'}), 404
    data = request.get_json(silent=True) or {}
    providers = data.get('providers')
    if providers is not None and not isinstance(providers, list):
        return jsonify({'error': 'providers must be a list'}), 400
    result = publish_service.enqueue_publish(
        company_key,
        job_id,
        providers=providers,
        auto_publish_only=False,
        operation='publish',
    )
    return jsonify(result), 202


@integrations_bp.post('/republish/<string:job_id>')
@require_recruiter
def republish_job(job_id: str):
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    if not _job_belongs_to_company(job_id, company_key, request.user):
        return jsonify({'error': 'Job not found'}), 404
    data = request.get_json(silent=True) or {}
    providers = data.get('providers')
    result = publish_service.enqueue_publish(
        company_key,
        job_id,
        providers=providers,
        auto_publish_only=False,
        operation='republish',
    )
    return jsonify(result), 202


@integrations_bp.post('/retry/<int:external_job_id>')
@require_recruiter
def retry_external_job(external_job_id: int):
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    result = publish_service.enqueue_retry(company_key, external_job_id)
    if not result:
        return jsonify({'error': 'External job not found'}), 404
    return jsonify(result), 202


@integrations_bp.get('/jobs')
@authenticate_token
def list_external_jobs():
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    job_id = request.args.get('jobId') or request.args.get('job_id')
    rows = repo.list_external_jobs(company_key, job_id=job_id)
    return jsonify({'jobs': [serialize_external_job(r) for r in rows]})


@integrations_bp.get('/logs')
@authenticate_token
def list_logs():
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    limit = request.args.get('limit', 50)
    provider = request.args.get('provider')
    try:
        limit_i = int(limit)
    except ValueError:
        limit_i = 50
    rows = repo.list_sync_logs(company_key, limit=limit_i, provider=provider)
    return jsonify({'logs': [serialize_log_row(r) for r in rows]})


@integrations_bp.get('/status')
@authenticate_token
def integration_status():
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    return jsonify(build_status(company_key))


@integrations_bp.get('/dashboard')
@authenticate_token
def integration_dashboard():
    company_key, _, err = _company_or_403(request.user)
    if err:
        return err
    return jsonify(build_dashboard(company_key))
