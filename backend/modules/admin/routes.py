"""
Admin routes: bulk resume parsing (proxy to Bulk-Resume-Parser API), job matches (ATS results).
All routes require HR role via require_hr middleware.
"""
from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename
from db import db_get, db_all, BACKEND, TRUE_SQL
from utils import authenticate_token, require_hr
from rbac import can_access_bulk_session, get_role, ROLE_HEAD_HR, is_read_only, get_user_id
from services.bulk_parsing_service import (
    upload_files as bulk_upload,
    get_progress as bulk_progress,
    stream_download as bulk_stream_download,
    ERROR_CODE_UNREACHABLE,
)

admin_bp = Blueprint('admin', __name__)

ALLOWED_BULK_EXTENSIONS = {'pdf', 'doc', 'docx'}


def _allowed_bulk_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_BULK_EXTENSIONS


# ============================================================================
# BULK RESUME PARSING - proxy to Bulk-Resume-Parser API (internal service)
# ============================================================================

@admin_bp.route('/bulk-parse/upload', methods=['POST'])
@authenticate_token
@require_hr
def bulk_parse_upload():
    """
    Upload multiple resume files for bulk parsing.
    Proxies to Bulk-Resume-Parser API; no duplicate parsing logic.
    """
    if is_read_only(request.user):
        return jsonify({'error': 'Read-only access'}), 403
    if 'files' not in request.files and not any(k.startswith('file') for k in request.files):
        return jsonify({'error': 'No files provided'}), 400
    files_from_request = request.files.getlist('files') or request.files.getlist('file')
    if not files_from_request:
        return jsonify({'error': 'No files provided'}), 400
    files_list = []
    for f in files_from_request:
        if f.filename and _allowed_bulk_file(f.filename):
            data = f.read()
            if data:
                files_list.append((secure_filename(f.filename), data))
    if not files_list:
        return jsonify({'error': 'No valid resume files (PDF/DOC/DOCX)'}), 400
    success, result = bulk_upload(files_list, append=request.form.get('append', 'false').lower() == 'true', started_by=get_user_id(request.user))
    if not success:
        code = result.get('code')
        if code == ERROR_CODE_UNREACHABLE or code == 'BULK_PARSER_NOT_CONFIGURED':
            return jsonify(result), 503
        return jsonify(result), 502
    return jsonify(result), 200


@admin_bp.route('/bulk-parse/progress/<job_id>', methods=['GET'])
@authenticate_token
@require_hr
def bulk_parse_progress(job_id):
    """Get bulk parsing job progress. Proxies to Bulk-Resume-Parser API."""
    from services.local_bulk_parser import get_local_progress
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
@require_hr
def bulk_parse_download(job_id):
    """Stream Excel download from Bulk-Resume-Parser. Proxies internally."""
    from services.local_bulk_parser import get_local_progress
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
@require_hr
def job_matches():
    """
    List jobs posted by this HR with application counts and shortlisted counts.
    Admin can then call GET /api/jobs/<job_id>/applications for full ATS results per job.
    """
    hr_id = request.user.get('hrId')
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
