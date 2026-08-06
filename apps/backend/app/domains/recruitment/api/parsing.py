"""
Resume and Job Description Parsing Routes.

Thin HTTP layer over the Document Intelligence Engine.
Frontend clients receive Form DTOs only — never raw TOON/AI output.
"""
from __future__ import annotations

import hmac
import os
import time
import uuid
from collections import defaultdict, deque

from flask import Blueprint, Response, jsonify, request, stream_with_context
from werkzeug.utils import secure_filename

from app.api.middleware.auth import authenticate_token, require_recruiter
from app.ai.document_intelligence.response import (
    build_jd_client_payload,
    build_resume_client_payload,
)
from app.ai.parser.engine import get_parse_job, run_jd_parse_pipeline, run_resume_parse_pipeline
from app.ai.parser.engine.confidence import calculate_confidence
from app.ai.parser.engine.progress import create_parse_job
from app.ai.toon.runtime import toon_loads_flex
from app.domains.identity.authorization.rbac import STAFF_ROLES, get_role, get_user_id


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
_public_parse_hits: dict[str, deque] = defaultdict(deque)

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


def _client_ip() -> str:
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or 'unknown'


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

    now = time.time()
    q = _public_parse_hits[ip]
    while q and now - q[0] > _PUBLIC_PARSE_WINDOW_SEC:
        q.popleft()
    if len(q) >= _PUBLIC_PARSE_LIMIT:
        return True
    q.append(now)
    return False


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
            }), 429

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
        print(f"Public resume parsing error: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


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
        print(f"Resume parsing error: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


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
        print(f"JD parsing error: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@parsing_bp.route('/parse/jobs/<job_id>/progress', methods=['GET'])
def parse_job_progress(job_id):
    """
    Poll stage progress for a single-file parse job.
    Returns events emitted by the Intelligence Engine.
    """
    job = get_parse_job(job_id)
    if not job:
        return jsonify({'status': 'error', 'error': 'Parse job not found'}), 404
    return jsonify({'status': 'ok', **job}), 200


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
    public_uploader_id = f"PUB{(uuid.uuid4().hex[:16]).upper()}"
    parse_job_id = create_parse_job('resume')

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
                    parse_job_id=parse_job_id,
                    on_stage=on_stage,
                )
            return run_resume_parse_pipeline(
                file_data,
                filename,
                uploader_id=public_uploader_id,
                uploader_role='public',
                candidate_id=None,
                enrichment_context=None,
                parse_job_id=parse_job_id,
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
            'X-Parse-Job-Id': parse_job_id,
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
    parse_job_id = create_parse_job('job_description')

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
                    parse_job_id=parse_job_id,
                    on_stage=on_stage,
                )
            return run_jd_parse_pipeline(
                file_data,
                filename,
                uploader_id=uploader_id,
                uploader_role=uploader_role,
                job_id=job_id,
                parse_job_id=parse_job_id,
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
            'X-Parse-Job-Id': parse_job_id,
        },
    )


@parsing_bp.route('/parsed/resume/<parsed_id>', methods=['GET'])
@authenticate_token
def get_parsed_resume(parsed_id):
    from app.database.connection.db import db_get

    try:
        result = db_get(
            "SELECT id, toon, confidence, model_version, created_at FROM parsed_resumes WHERE id = ?",
            (parsed_id,),
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
        return jsonify({'status': 'error', 'error': str(e)}), 500


@parsing_bp.route('/parsed/jd/<parsed_id>', methods=['GET'])
@authenticate_token
def get_parsed_jd(parsed_id):
    from app.database.connection.db import db_get

    try:
        result = db_get(
            "SELECT id, toon, confidence, model_version, created_at FROM parsed_jds WHERE id = ?",
            (parsed_id,),
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
        return jsonify({'status': 'error', 'error': str(e)}), 500
