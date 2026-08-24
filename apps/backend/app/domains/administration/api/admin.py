"""
Admin routes: bulk resume parsing (proxy to Bulk-Resume-Parser API), job matches (ATS results).
All routes require RECRUITER or HEAD_HR via require_recruiter middleware.
"""
from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename
from app.database.connection.db import db_get, db_all, BACKEND, TRUE_SQL
from app.api.middleware.auth import authenticate_token, require_recruiter
from app.domains.identity.authorization.rbac import can_access_bulk_session, get_role, ROLE_HEAD_HR, is_read_only, get_user_id
from app.domains.administration.services.bulk_parsing import (
    create_job as bulk_create_job,
    upload_chunk as bulk_upload_chunk,
    start_job as bulk_start_job,
    pause_job as bulk_pause_job,
    resume_job as bulk_resume_job,
    upload_files as bulk_upload,
    get_progress as bulk_progress,
    stream_download as bulk_stream_download,
    ERROR_CODE_UNREACHABLE,
)

admin_bp = Blueprint('admin', __name__)

ALLOWED_BULK_EXTENSIONS = {'pdf', 'doc', 'docx'}


def _allowed_bulk_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_BULK_EXTENSIONS


def _is_zip_filename(filename):
    return bool(filename) and filename.rsplit('.', 1)[-1].lower() == 'zip'


def _collect_resume_files_from_request():
    """Return list of (secure_filename, bytes) from multipart 'files'/'file' parts."""
    files_from_request = request.files.getlist('files') or request.files.getlist('file')
    files_list = []
    for f in files_from_request:
        if f.filename and _allowed_bulk_file(f.filename):
            data = f.read()
            if data:
                files_list.append((secure_filename(f.filename), data))
    return files_list


def _collect_zip_from_request():
    """Return first ZIP file bytes from multipart, or None."""
    for key in ('zip', 'files', 'file'):
        for f in request.files.getlist(key):
            if f.filename and _is_zip_filename(f.filename):
                data = f.read()
                if data:
                    return data
    return None


# ============================================================================
# BULK RESUME PARSING - chunked upload + ZIP + local fallback
# ============================================================================

@admin_bp.route('/bulk-parse/jobs', methods=['POST'])
@authenticate_token
@require_recruiter
def bulk_parse_create_job():
    """Create an empty bulk parse job for chunked / ZIP uploads."""
    if is_read_only(request.user):
        return jsonify({'error': 'Read-only access'}), 403
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    append = bool(body.get('append')) or (request.form.get('append', 'false').lower() == 'true')
    success, result = bulk_create_job(started_by=get_user_id(request.user), append=append)
    if not success:
        return jsonify(result), 502
    return jsonify(result), 200


@admin_bp.route('/bulk-parse/upload', methods=['POST'])
@authenticate_token
@require_recruiter
def bulk_parse_upload():
    """
    Upload resumes for bulk parsing.
    - With job_id: append a chunk of files or a ZIP to that job (does not start).
    - Without job_id: legacy one-shot upload (all files) that starts immediately.
    Optional form finalize=true starts the job after this chunk.
    """
    if is_read_only(request.user):
        return jsonify({'error': 'Read-only access'}), 403

    append = request.form.get('append', 'false').lower() == 'true'
    finalize = request.form.get('finalize', 'false').lower() == 'true'
    job_id = (request.form.get('job_id') or '').strip() or None
    started_by = get_user_id(request.user)

    zip_bytes = _collect_zip_from_request()
    files_list = _collect_resume_files_from_request() if not zip_bytes else []

    if not zip_bytes and not files_list:
        if 'files' not in request.files and 'file' not in request.files and 'zip' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        return jsonify({'error': 'No valid resume files (PDF/DOC/DOCX) or ZIP'}), 400

    # Chunked / ZIP path
    if job_id:
        success, result = bulk_upload_chunk(
            job_id,
            files_list,
            started_by=started_by,
            zip_bytes=zip_bytes,
        )
        if not success:
            return jsonify(result), 400
        if finalize:
            ok_start, start_result = bulk_start_job(job_id, append=append if append else None)
            if not ok_start:
                return jsonify(start_result), 400
            return jsonify(start_result), 200
        return jsonify(result), 200

    # Legacy one-shot: create + stage + start (or ZIP as one-shot)
    if zip_bytes:
        ok, created = bulk_create_job(started_by=started_by, append=append)
        if not ok:
            return jsonify(created), 502
        job_id = created['job_id']
        success, result = bulk_upload_chunk(job_id, [], started_by=started_by, zip_bytes=zip_bytes)
        if not success:
            return jsonify(result), 400
        ok_start, start_result = bulk_start_job(job_id, append=append)
        if not ok_start:
            return jsonify(start_result), 400
        return jsonify(start_result), 200

    success, result = bulk_upload(files_list, append=append, started_by=started_by)
    if not success:
        code = result.get('code')
        if code == ERROR_CODE_UNREACHABLE or code == 'BULK_PARSER_NOT_CONFIGURED':
            return jsonify(result), 503
        return jsonify(result), 502
    return jsonify(result), 200


@admin_bp.route('/bulk-parse/start/<job_id>', methods=['POST'])
@authenticate_token
@require_recruiter
def bulk_parse_start(job_id):
    """Start processing a previously staged bulk parse job."""
    if is_read_only(request.user):
        return jsonify({'error': 'Read-only access'}), 403
    from app.workers.bulk_parser import get_local_progress

    ok_local, local_job = get_local_progress(job_id, check_only=True)
    if ok_local:
        started_by = local_job.get('started_by')
        if started_by and not can_access_bulk_session(request.user, started_by):
            return jsonify({'error': 'Access denied'}), 403
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    append = body.get('append')
    if append is None:
        append_form = request.form.get('append')
        if append_form is not None:
            append = append_form.lower() == 'true'
    success, result = bulk_start_job(job_id, append=append)
    if not success:
        return jsonify(result), 400
    return jsonify(result), 200


@admin_bp.route('/bulk-parse/pause/<job_id>', methods=['POST'])
@authenticate_token
@require_recruiter
def bulk_parse_pause(job_id):
    """Pause a running bulk parse job (finishes in-flight files, then stops)."""
    if is_read_only(request.user):
        return jsonify({'error': 'Read-only access'}), 403
    from app.workers.bulk_parser import get_local_progress

    ok_local, local_job = get_local_progress(job_id, check_only=True)
    if ok_local:
        started_by = local_job.get('started_by')
        if started_by and not can_access_bulk_session(request.user, started_by):
            return jsonify({'error': 'Access denied'}), 403
    success, result = bulk_pause_job(job_id)
    if not success:
        return jsonify(result), 400
    return jsonify(result), 200


@admin_bp.route('/bulk-parse/resume/<job_id>', methods=['POST'])
@authenticate_token
@require_recruiter
def bulk_parse_resume(job_id):
    """Resume a paused bulk parse job."""
    if is_read_only(request.user):
        return jsonify({'error': 'Read-only access'}), 403
    from app.workers.bulk_parser import get_local_progress

    ok_local, local_job = get_local_progress(job_id, check_only=True)
    if ok_local:
        started_by = local_job.get('started_by')
        if started_by and not can_access_bulk_session(request.user, started_by):
            return jsonify({'error': 'Access denied'}), 403
    success, result = bulk_resume_job(job_id)
    if not success:
        return jsonify(result), 400
    return jsonify(result), 200


@admin_bp.route('/bulk-parse/progress/<job_id>', methods=['GET'])
@authenticate_token
@require_recruiter
def bulk_parse_progress(job_id):
    """Get bulk parsing job progress. Proxies to Bulk-Resume-Parser API."""
    from app.workers.bulk_parser import get_local_progress
    ok_local, local_job = get_local_progress(job_id, check_only=True)
    if ok_local:
        started_by = local_job.get('started_by')
        if started_by and not can_access_bulk_session(request.user, started_by):
            return jsonify({'error': 'Access denied'}), 403
    success, result = bulk_progress(job_id, user=request.user)
    if not success:
        if result.get('code') == ERROR_CODE_UNREACHABLE or result.get('code') == 'BULK_PARSER_NOT_CONFIGURED':
            return jsonify(result), 503
        return jsonify(result), 404 if result.get('error') == 'Job not found' else 502
    return jsonify(result), 200


@admin_bp.route('/bulk-parse/download/<job_id>', methods=['GET'])
@authenticate_token
@require_recruiter
def bulk_parse_download(job_id):
    """Stream Excel download from Bulk-Resume-Parser. Proxies internally."""
    from app.workers.bulk_parser import get_local_progress
    ok_local, local_job = get_local_progress(job_id, check_only=True)
    if ok_local:
        started_by = local_job.get('started_by')
        if started_by and not can_access_bulk_session(request.user, started_by):
            return jsonify({'error': 'Access denied'}), 403
    success, payload = bulk_stream_download(job_id, user=request.user)
    if not success:
        if payload.get('code') == ERROR_CODE_UNREACHABLE or payload.get('code') == 'BULK_PARSER_NOT_CONFIGURED':
            return jsonify(payload), 503
        return jsonify(payload), 404 if 'not found' in str(payload.get('error', '')).lower() else 502
    iterator, filename, content_type = payload
    return Response(
        iterator,
        mimetype=content_type,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


# ============================================================================
# JOB MATCHES - list jobs with ATS results for admin
# ============================================================================

@admin_bp.route('/job-matches', methods=['GET'])
@authenticate_token
@require_recruiter
def job_matches():
    """
    List jobs posted by this HR with application counts and shortlisted counts.
    Admin can then call GET /api/jobs/<job_id>/applications for full ATS results per job.
    """
    hr_id = get_user_id(request.user)
    if not hr_id:
        return jsonify({'error': 'HR user required'}), 403
    role = get_role(request.user)
    if role == ROLE_HEAD_HR:
        jobs = db_all(
            '''
            SELECT j.jdid, j.title, j.company, j.location, j.enabled,
                   (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.jdid) as application_count,
                   (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.jdid AND a.shortlisted = ''' + TRUE_SQL + ''') as shortlisted_count
            FROM jobs j
            ORDER BY j.posted_on DESC
            '''
        )
    else:
        jobs = db_all(
            '''
            SELECT j.jdid, j.title, j.company, j.location, j.enabled,
                   (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.jdid) as application_count,
                   (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.jdid AND a.shortlisted = ''' + TRUE_SQL + ''') as shortlisted_count
            FROM jobs j
            WHERE j.posted_by = ?
            ORDER BY j.posted_on DESC
            ''',
            (hr_id,),
        )
    return jsonify({
        'jobs': [
            {
                'jobId': j['jdid'],
                'title': j['title'],
                'company': j.get('company'),
                'location': j.get('location'),
                'enabled': bool(j.get('enabled')),
                'applicationCount': j.get('application_count') or 0,
                'shortlistedCount': j.get('shortlisted_count') or 0,
            }
            for j in jobs
        ],
    }), 200
