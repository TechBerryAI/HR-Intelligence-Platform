"""
Resume and Job Description Parsing Routes.

Thin HTTP layer over the Document Intelligence Engine.
Frontend clients receive Form DTOs only — never raw TOON/AI output.
"""
from __future__ import annotations

import hmac
import logging
import os
import time
import uuid

from flask import Blueprint, Response, jsonify, request, stream_with_context
from werkzeug.utils import secure_filename

from app.api.middleware.auth import authenticate_token, require_recruiter
from app.ai.document_intelligence.response import (
    build_jd_client_payload,
    build_resume_client_payload,
)
from app.ai.parser.engine import get_parse_job, run_jd_parse_pipeline, run_resume_parse_pipeline
from app.ai.parser.engine.confidence import calculate_confidence
from app.ai.toon.runtime import toon_loads_flex
from app.core import shared_store
from app.domains.identity.authorization.rbac import STAFF_ROLES, get_role, get_user_id

logger = logging.getLogger(__name__)


def _resume_client(body: dict, status: int):
    if status != 200 or body.get('status') != 'ok':
        return jsonify(body), status
    return jsonify(build_resume_client_payload(body)), status


def _jd_client(body: dict, status: int):
    if status != 200 or body.get('status') != 'ok':
        return jsonify(body), status
    return jsonify(build_jd_client_payload(body)), status

parsing_bp = Blueprint('parsing', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

_PUBLIC_PARSE_LIMIT = int(os.getenv('PUBLIC_PARSE_RATE_LIMIT', '10'))
_PUBLIC_PARSE_WINDOW_SEC = int(os.getenv('PUBLIC_PARSE_RATE_WINDOW_SEC', '600'))
_VALIDATION_TOKEN = os.getenv('DOCUMENT_INTELLIGENCE_VALIDATION_TOKEN', '')

MIME_TYPE_MAP = {
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'doc': 'application/msword',
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _reject_legacy_doc(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext == 'doc':
        return jsonify({
            'status': 'error',
            'error': 'Legacy .doc format is not supported. Please use DOCX or PDF.',
        }), 400
    return None


def get_mime_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return MIME_TYPE_MAP.get(ext, 'application/octet-stream')


def _trust_proxy_headers() -> bool:
    return os.getenv('TRUST_PROXY_HEADERS', '').strip().lower() in ('1', 'true', 'yes', 'on')


def _client_ip() -> str:
    if _trust_proxy_headers():
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            return forwarded.split(',')[0].strip() or (request.remote_addr or 'unknown')
    return request.remote_addr or 'unknown'


def _reject_public_oversize():
    cl = request.content_length
    if cl is not None and cl > MAX_FILE_SIZE:
        return jsonify({
            'status': 'error',
            'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB',
        }), 413
    return None


def _generic_parse_error(exc: Exception, where: str):
    logger.exception('%s', where)
    return jsonify({'status': 'error', 'error': 'Internal server error'}), 500


def _public_parse_rate_limited(ip: str) -> bool:
    # Corpus E2E validation: shared secret or loopback under validation payload mode.
    header_token = request.headers.get('X-Validation-Token', '')
    if _VALIDATION_TOKEN and header_token and hmac.compare_digest(header_token, _VALIDATION_TOKEN):
        return False
    validation_payload = os.getenv('DOCUMENT_INTELLIGENCE_VALIDATION_PAYLOAD', '').lower() in (
        '1',
        'true',
        'yes',
    )
    if validation_payload and ip in ('127.0.0.1', '::1', 'localhost'):
        return False

    return shared_store.rate_limit_hit(
        f'public_parse:{ip}',
        _PUBLIC_PARSE_LIMIT,
        _PUBLIC_PARSE_WINDOW_SEC,
    )


# Re-export for tests / bulk workers that import from this module
__all__ = [
    'parsing_bp',
    'run_resume_parse_pipeline',
    'run_jd_parse_pipeline',
    'calculate_confidence',
]


@parsing_bp.route('/parse/resume/public', methods=['POST'])
def parse_resume_public():
    """Public resume parse for apply-form autofill (no auth). Rate-limited by IP."""
    try:
        ip = _client_ip()
        if _public_parse_rate_limited(ip):
            return jsonify({
                'status': 'error',
                'error': 'Too many resume parse requests. Please try again later.',
                'pid': os.getpid(),
            }), 429

        oversize = _reject_public_oversize()
        if oversize:
            return oversize

        if 'file' not in request.files:
            return jsonify({'status': 'error', 'error': 'No file provided', 'pid': os.getpid()}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'error': 'No file selected'}), 400

        doc_reject = _reject_legacy_doc(file.filename)
        if doc_reject:
            return doc_reject

        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
            }), 400

        file_data = file.read()
        if len(file_data) > MAX_FILE_SIZE:
            return jsonify({
                'status': 'error',
                'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB',
            }), 413
        filename = secure_filename(file.filename)
        public_uploader_id = f"PUB{(uuid.uuid4().hex[:16]).upper()}"

        body, status = run_resume_parse_pipeline(
            file_data,
            filename,
            uploader_id=public_uploader_id,
            uploader_role='public',
            candidate_id=None,
            enrichment_context=None,
        )
        return _resume_client(body, status)
    except Exception as e:
        return _generic_parse_error(e, 'Public resume parsing error')


@parsing_bp.route('/parse/resume', methods=['POST'])
@authenticate_token
def parse_resume_upload():
    """Upload and parse resume (authenticated staff). POST /api/parse/resume"""
    try:
        current_user = request.user

        if 'file' not in request.files:
            return jsonify({'status': 'error', 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'error': 'No file selected'}), 400

        doc_reject = _reject_legacy_doc(file.filename)
        if doc_reject:
            return doc_reject

        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
            }), 400

        file_data = file.read()
        filename = secure_filename(file.filename)

        uploader_id = get_user_id(current_user)
        jwt_role = get_role(current_user)
        if not uploader_id:
            return jsonify({
                'status': 'error',
                'error': 'User ID not found in authentication token',
            }), 401

        uploader_role = 'recruiter' if jwt_role in STAFF_ROLES else 'recruiter'
        candidate_id = request.form.get('candidate_id') or None

        body, status = run_resume_parse_pipeline(
            file_data,
            filename,
            uploader_id=uploader_id,
            uploader_role=uploader_role,
            candidate_id=candidate_id,
            enrichment_context=None,
        )
        return _resume_client(body, status)
    except Exception as e:
        return _generic_parse_error(e, 'Resume parsing error')


@parsing_bp.route('/parse/jd', methods=['POST'])
@authenticate_token
@require_recruiter
def parse_jd_upload():
    """Upload and parse job description. POST /api/parse/jd"""
    try:
        current_user = request.user

        if 'file' not in request.files:
            return jsonify({'status': 'error', 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'status': 'error', 'error': 'No file selected'}), 400

        doc_reject = _reject_legacy_doc(file.filename)
        if doc_reject:
            return doc_reject

        if not allowed_file(file.filename):
            return jsonify({
                'status': 'error',
                'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
            }), 400

        file_data = file.read()
        if len(file_data) > MAX_FILE_SIZE:
            return jsonify({
                'status': 'error',
                'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB',
            }), 400

        filename = secure_filename(file.filename)
        uploader_id = get_user_id(current_user)
        jwt_role = get_role(current_user)
        uploader_role = 'recruiter' if jwt_role in STAFF_ROLES else 'candidate'

        if not uploader_id:
            return jsonify({
                'status': 'error',
                'error': 'User ID not found in authentication token',
            }), 401

        job_id = request.form.get('job_id')

        body, status = run_jd_parse_pipeline(
            file_data,
            filename,
            uploader_id=uploader_id,
            uploader_role=uploader_role,
            job_id=job_id,
        )
        return _jd_client(body, status)
    except Exception as e:
        return _generic_parse_error(e, 'JD parsing error')


@parsing_bp.route('/parse/jobs/<job_id>/progress', methods=['GET'])
def parse_job_progress(job_id):
    """
    Poll stage progress for a single-file parse job.
    Returns events emitted by the Intelligence Engine.
    """
    job = get_parse_job(job_id)
    if not job:
        return jsonify({'status': 'error', 'error': 'Parse job not found'}), 404
    return jsonify({
        'status': 'ok',
        'id': job['id'],
        'doc_type': job.get('doc_type'),
        'job_status': job.get('status'),
        'events': job.get('events') or [],
        'error': job.get('error'),
    }), 200


@parsing_bp.route('/parse/resume/public/stream', methods=['POST'])
def parse_resume_public_stream():
    """
    SSE stream of stage events for public resume parse, ending with final result JSON.
    Event types: stage | result | error
    """
    ip = _client_ip()
    if _public_parse_rate_limited(ip):
        return jsonify({
            'status': 'error',
            'error': 'Too many resume parse requests. Please try again later.',
        }), 429

    oversize = _reject_public_oversize()
    if oversize:
        return oversize

    if 'file' not in request.files:
        return jsonify({'status': 'error', 'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'status': 'error', 'error': 'No file selected'}), 400

    doc_reject = _reject_legacy_doc(file.filename)
    if doc_reject:
        return doc_reject

    if not allowed_file(file.filename):
        return jsonify({
            'status': 'error',
            'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
        }), 400

    file_data = file.read()
    if len(file_data) > MAX_FILE_SIZE:
        return jsonify({
            'status': 'error',
            'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB',
        }), 413
    filename = secure_filename(file.filename)
    public_uploader_id = f"PUB{(uuid.uuid4().hex[:16]).upper()}"

    def generate():
        import json

        events_q: list = []

        def on_stage(event):
            events_q.append(event)

        # Run pipeline synchronously while flushing queued stage events
        from concurrent.futures import ThreadPoolExecutor

        from app.core.request_context import get_timing_context, run_in_timing_context

        timing_ctx = get_timing_context()

        def _run_pipeline():
            if timing_ctx is not None:
                return run_in_timing_context(
                    timing_ctx,
                    run_resume_parse_pipeline,
                    file_data,
                    filename,
                    uploader_id=public_uploader_id,
                    uploader_role='public',
                    candidate_id=None,
                    enrichment_context=None,
                    on_stage=on_stage,
                )
            return run_resume_parse_pipeline(
                file_data,
                filename,
                uploader_id=public_uploader_id,
                uploader_role='public',
                candidate_id=None,
                enrichment_context=None,
                on_stage=on_stage,
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_pipeline)
            while not future.done():
                while events_q:
                    ev = events_q.pop(0)
                    yield f"event: stage\ndata: {json.dumps(ev.to_dict(), default=str)}\n\n"
                time.sleep(0.05)
            while events_q:
                ev = events_q.pop(0)
                yield f"event: stage\ndata: {json.dumps(ev.to_dict(), default=str)}\n\n"
            body, status = future.result()
            if status == 200:
                payload = build_resume_client_payload(body)
                yield f"event: result\ndata: {json.dumps(payload, default=str)}\n\n"
            else:
                yield f"event: error\ndata: {json.dumps(body, default=str)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


@parsing_bp.route('/parse/jd/stream', methods=['POST'])
@authenticate_token
@require_recruiter
def parse_jd_stream():
    """SSE stream of stage events for JD parse."""
    current_user = request.user
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'status': 'error', 'error': 'No file selected'}), 400

    doc_reject = _reject_legacy_doc(file.filename)
    if doc_reject:
        return doc_reject

    if not allowed_file(file.filename):
        return jsonify({
            'status': 'error',
            'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}',
        }), 400

    file_data = file.read()
    filename = secure_filename(file.filename)
    uploader_id = get_user_id(current_user)
    jwt_role = get_role(current_user)
    uploader_role = 'recruiter' if jwt_role in STAFF_ROLES else 'candidate'
    if not uploader_id:
        return jsonify({'status': 'error', 'error': 'User ID not found'}), 401

    job_id = request.form.get('job_id')

    def generate():
        import json
        from concurrent.futures import ThreadPoolExecutor

        from app.core.request_context import get_timing_context, run_in_timing_context

        events_q: list = []

        def on_stage(event):
            events_q.append(event)

        timing_ctx = get_timing_context()

        def _run_pipeline():
            if timing_ctx is not None:
                return run_in_timing_context(
                    timing_ctx,
                    run_jd_parse_pipeline,
                    file_data,
                    filename,
                    uploader_id=uploader_id,
                    uploader_role=uploader_role,
                    job_id=job_id,
                    on_stage=on_stage,
                )
            return run_jd_parse_pipeline(
                file_data,
                filename,
                uploader_id=uploader_id,
                uploader_role=uploader_role,
                job_id=job_id,
                on_stage=on_stage,
            )

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_pipeline)
            while not future.done():
                while events_q:
                    ev = events_q.pop(0)
                    yield f"event: stage\ndata: {json.dumps(ev.to_dict(), default=str)}\n\n"
                time.sleep(0.05)
            while events_q:
                ev = events_q.pop(0)
                yield f"event: stage\ndata: {json.dumps(ev.to_dict(), default=str)}\n\n"
            body, status = future.result()
            if status == 200:
                payload = build_jd_client_payload(body)
                yield f"event: result\ndata: {json.dumps(payload, default=str)}\n\n"
            else:
                yield f"event: error\ndata: {json.dumps(body, default=str)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


@parsing_bp.route('/parsed/resume/<parsed_id>', methods=['GET'])
@authenticate_token
def get_parsed_resume(parsed_id):
    from app.database.connection.db import db_get
    from app.domains.identity.services.organizations import require_organization_id
    from app.domains.identity.authorization.rbac import get_user_id, get_role, ROLE_RECRUITER

    try:
        org_id, org_err = require_organization_id(request.user)
        if org_err:
            return org_err
        result = db_get(
            """
            SELECT pr.id, pr.toon, pr.confidence, pr.model_version, pr.created_at, pr.candidate_id
            FROM parsed_resumes pr
            WHERE pr.id = ?
              AND (
                EXISTS (
                  SELECT 1 FROM applications a
                  JOIN jobs j ON j.jdid = a.job_id
                  WHERE a.candidate_id = pr.candidate_id AND j.organization_id = ?
                )
                OR EXISTS (
                  SELECT 1 FROM raw_files rf
                  WHERE rf.id = pr.raw_file_id AND rf.uploader_id = ?
                )
              )
            """,
            (parsed_id, org_id, get_user_id(request.user)),
        )
        if not result:
            return jsonify({'status': 'error', 'error': 'Parsed resume not found'}), 404
        toon = toon_loads_flex(result['toon'])
        payload = build_resume_client_payload({
            'status': 'ok',
            'parsed_id': result['id'],
            'toon': toon,
            'confidence': result['confidence'],
            'model_version': result['model_version'],
        })
        payload['created_at'] = (
            result['created_at'].isoformat()
            if hasattr(result['created_at'], 'isoformat')
            else str(result['created_at'])
        )
        return jsonify(payload), 200
    except Exception as e:
        return _generic_parse_error(e, 'get_parsed_resume')


@parsing_bp.route('/parsed/jd/<parsed_id>', methods=['GET'])
@authenticate_token
def get_parsed_jd(parsed_id):
    from app.database.connection.db import db_get
    from app.domains.identity.services.organizations import require_organization_id
    from app.domains.identity.authorization.rbac import get_user_id

    try:
        org_id, org_err = require_organization_id(request.user)
        if org_err:
            return org_err
        result = db_get(
            """
            SELECT pj.id, pj.toon, pj.confidence, pj.model_version, pj.created_at
            FROM parsed_jds pj
            WHERE pj.id = ?
              AND (
                EXISTS (
                  SELECT 1 FROM jobs j
                  WHERE j.parsed_jd_id = pj.id AND j.organization_id = ?
                )
                OR EXISTS (
                  SELECT 1 FROM raw_files rf
                  WHERE rf.id = pj.raw_file_id AND rf.uploader_id = ?
                )
              )
            """,
            (parsed_id, org_id, get_user_id(request.user)),
        )
        if not result:
            return jsonify({'status': 'error', 'error': 'Parsed JD not found'}), 404
        toon = toon_loads_flex(result['toon'])
        payload = build_jd_client_payload({
            'status': 'ok',
            'parsed_id': result['id'],
            'toon': toon,
            'confidence': result['confidence'],
            'model_version': result['model_version'],
        })
        payload['created_at'] = (
            result['created_at'].isoformat()
            if hasattr(result['created_at'], 'isoformat')
            else str(result['created_at'])
        )
        return jsonify(payload), 200
    except Exception as e:
        return _generic_parse_error(e, 'get_parsed_jd')
