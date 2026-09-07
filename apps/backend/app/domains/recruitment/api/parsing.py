"""
Resume and Job Description Parsing Routes.

Thin HTTP layer over the Document Intelligence Engine.
Frontend clients receive Form DTOs only — never raw TOON/AI output.
"""
from __future__ import annotations

import hmac
import logging
import os
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

_SSE_PAD = ':' + (' ' * 2048) + '\n\n'
_SSE_HEADERS = {
    'Cache-Control': 'no-cache, no-transform',
    'X-Accel-Buffering': 'no',
}


def _safe_error_body(body: dict, status: int) -> dict:
    if status < 500:
        return body
    out = {'status': 'error', 'error': 'Internal server error'}
    if body.get('parse_job_id'):
        out['parse_job_id'] = body['parse_job_id']
    return out


def _resume_client(body: dict, status: int):
    if status >= 500:
        return jsonify(_safe_error_body(body, status)), status
    if status != 200 or body.get('status') != 'ok':
        return jsonify(body), status
    return jsonify(build_resume_client_payload(body)), status


def _jd_client(body: dict, status: int):
    if status >= 500:
        return jsonify(_safe_error_body(body, status)), status
    if status != 200 or body.get('status') != 'ok':
        return jsonify(body), status
    return jsonify(build_jd_client_payload(body)), status

parsing_bp = Blueprint('parsing', __name__)

# Image resumes (PNG/JPG) are rejected — OCR quality is too unreliable for apply/autofill.
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'webp'}
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


def _sse_pack(event_name: str, payload: dict) -> str:
    import json

    return f"event: {event_name}\ndata: {json.dumps(payload, default=str)}\n\n{_SSE_PAD}"


def iter_parse_sse(run_with_on_stage, build_ok_payload, timing_ctx=None):
    """Yield SSE chunks while a parse pipeline runs in a worker thread.

    Stage events are flushed as they happen so the upload overlay can track
    live progress through Vite / reverse-proxy buffers.
    """
    import time as _time
    from concurrent.futures import ThreadPoolExecutor
    from queue import Empty, Queue

    from app.core.request_context import get_timing_context, run_in_timing_context
    from app.core.timing_collector import record_pipeline_stage

    events_q: Queue = Queue()
    bound_ctx = timing_ctx if timing_ctx is not None else get_timing_context()

    def on_stage(event):
        events_q.put(event)

    def _run():
        if bound_ctx is not None:
            return run_in_timing_context(bound_ctx, run_with_on_stage, on_stage)
        return run_with_on_stage(on_stage)

    yield _SSE_PAD
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        while not future.done():
            try:
                ev = events_q.get(timeout=0.25)
                yield _sse_pack('stage', ev.to_dict())
            except Empty:
                # Pad pings too — Vite / proxies otherwise buffer tiny comments
                # and the overlay stays on the last flushed stage (usually "text").
                yield _SSE_PAD
        while True:
            try:
                ev = events_q.get_nowait()
                yield _sse_pack('stage', ev.to_dict())
            except Empty:
                break
        t_deliver = _time.perf_counter()
        try:
            body, status = future.result()
        except Exception:
            logger.exception('Parse SSE worker failed')
            record_pipeline_stage(
                'deliver',
                'failed',
                duration_ms=(_time.perf_counter() - t_deliver) * 1000.0,
            )
            yield _sse_pack('error', {'status': 'error', 'error': 'Internal server error'})
            return
        if status == 200:
            payload = build_ok_payload(body)
            record_pipeline_stage(
                'deliver',
                'completed',
                duration_ms=(_time.perf_counter() - t_deliver) * 1000.0,
            )
            yield _sse_pack('result', payload)
        else:
            record_pipeline_stage(
                'deliver',
                'failed',
                duration_ms=(_time.perf_counter() - t_deliver) * 1000.0,
            )
            yield _sse_pack('error', body)


def _bind_sse_timing():
    """Keep Developer Mode session open for the whole SSE stream (not view return)."""
    import time as _time

    from app.core.developer_mode import is_developer_mode_enabled
    from app.core.request_context import get_timing_context
    from app.core.timing_collector import record_pipeline_stage

    ctx = get_timing_context()
    rid = getattr(request, 'timing_request_id', None) or (ctx.request_id if ctx else None)
    started = getattr(request, 'timing_started_at', None)
    request.timing_keep_open = True
    if is_developer_mode_enabled() and started is not None:
        record_pipeline_stage(
            'upload',
            'completed',
            duration_ms=(_time.perf_counter() - started) * 1000.0,
        )
    return ctx, rid, started


def _end_sse_timing(rid, started):
    import time as _time

    from app.core.developer_mode import is_developer_mode_enabled
    from app.core.timing_collector import timing_collector

    if not rid or not is_developer_mode_enabled():
        return
    wall_ms = None
    if started is not None:
        wall_ms = (_time.perf_counter() - started) * 1000.0
    timing_collector.end_session(rid, wall_duration_ms=wall_ms)


def _sse_generate(run_with_on_stage, build_ok_payload):
    """Bind timing context in the view, restore it in the generator, end after stream."""
    from app.core.developer_mode import is_developer_mode_enabled
    from app.core.request_context import reset_timing_context, set_timing_context

    ctx, rid, started = _bind_sse_timing()

    def _build(body):
        payload = build_ok_payload(body)
        if rid and is_developer_mode_enabled():
            payload['timing_request_id'] = rid
        return payload

    def generate():
        token = set_timing_context(ctx) if ctx is not None else None
        try:
            yield from iter_parse_sse(run_with_on_stage, _build, timing_ctx=ctx)
        finally:
            try:
                _end_sse_timing(rid, started)
            finally:
                if token is not None:
                    try:
                        reset_timing_context(token)
                    except Exception:
                        set_timing_context(None)

    return generate


def _sse_response(generate):
    # Do not set direct_passthrough: Werkzeug then skips stream_with_context and
    # closes the socket after headers (browser: "Failed to fetch" / network error).
    resp = Response(
        stream_with_context(generate()),
        mimetype='text/event-stream; charset=utf-8',
        headers=_SSE_HEADERS,
    )
    resp.implicit_sequence_conversion = False
    return resp


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

    def _run(on_stage):
        return run_resume_parse_pipeline(
            file_data,
            filename,
            uploader_id=public_uploader_id,
            uploader_role='public',
            candidate_id=None,
            enrichment_context=None,
            on_stage=on_stage,
        )

    return _sse_response(_sse_generate(_run, build_resume_client_payload))


@parsing_bp.route('/parse/resume/stream', methods=['POST'])
@authenticate_token
def parse_resume_stream():
    """SSE stream of stage events for authenticated resume parse."""
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
    if not uploader_id:
        return jsonify({'status': 'error', 'error': 'User ID not found in authentication token'}), 401

    uploader_role = 'recruiter' if jwt_role in STAFF_ROLES else 'recruiter'
    candidate_id = request.form.get('candidate_id') or None

    def _run(on_stage):
        return run_resume_parse_pipeline(
            file_data,
            filename,
            uploader_id=uploader_id,
            uploader_role=uploader_role,
            candidate_id=candidate_id,
            enrichment_context=None,
            on_stage=on_stage,
        )

    return _sse_response(_sse_generate(_run, build_resume_client_payload))


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

    def _run(on_stage):
        return run_jd_parse_pipeline(
            file_data,
            filename,
            uploader_id=uploader_id,
            uploader_role=uploader_role,
            job_id=job_id,
            on_stage=on_stage,
        )

    return _sse_response(_sse_generate(_run, build_jd_client_payload))


@parsing_bp.route('/parse/timing-client', methods=['POST'])
def parse_timing_client():
    """
    Browser timings from file-chosen until autofill is visible.

    No auth: the parse request_id is unguessable and only attaches to an
    in-memory Developer Mode session on this process.
    """
    from app.core.developer_mode import is_developer_mode_enabled
    from app.core.timing_collector import attach_client_timings

    if not is_developer_mode_enabled():
        return jsonify({'ok': True, 'ignored': True}), 200
    data = request.get_json(silent=True) or {}
    rid = str(data.get('request_id') or data.get('timing_request_id') or '').strip()
    if not rid or len(rid) > 64:
        return jsonify({'ok': False, 'error': 'invalid request'}), 400
    if not attach_client_timings(rid, data):
        return jsonify({'ok': False, 'error': 'unknown request'}), 404
    return jsonify({'ok': True}), 200


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
