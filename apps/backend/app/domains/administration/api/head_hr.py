"""
Head HR blueprint — executive analytics and org-wide administration.
"""
import bcrypt
from functools import wraps
from flask import Blueprint, jsonify, request

from app.database.connection.db import db_all, db_get, db_run
from app.ai.toon.runtime import toon_loads_flex
from app.api.middleware.auth import authenticate_token, require_head_hr
from app.domains.identity.authorization.rbac import is_head_hr, require_analytics_read, is_read_only
from app.domains.recruitment.services.job_delete import cascade_delete_job
from app.domains.recruitment.services.ats_service import sync_application_match_score

head_hr_bp = Blueprint('head_hr', __name__)


def allow_options_no_auth(f):
    """Return 204 for OPTIONS (CORS preflight) without running auth."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == 'OPTIONS':
            return '', 204
        return f(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Stats / Dashboard
# ---------------------------------------------------------------------------

@head_hr_bp.get('/stats')
@require_analytics_read
def get_stats():
    # Match Admins page: every hr_signup row (including CEO / Head HR / recruiters).
    total_admins = db_get(
        "SELECT COUNT(*) AS cnt FROM hr_signup WHERE COALESCE(account_status, 'active') = 'active'",
        (),
    )
    # Match jobs "Candidates" meaning: people who actually applied (not orphan signup rows
    # left by parse harness / abandoned apply drafts).
    total_candidates = db_get(
        'SELECT COUNT(DISTINCT candidate_id) AS cnt FROM applications WHERE candidate_id IS NOT NULL',
        (),
    )
    total_jobs = db_get('SELECT COUNT(*) AS cnt FROM jobs', ())
    total_applications = db_get('SELECT COUNT(*) AS cnt FROM applications', ())
    active_jobs = db_get('SELECT COUNT(*) AS cnt FROM jobs WHERE enabled = true', ())
    shortlisted = db_get('SELECT COUNT(*) AS cnt FROM applications WHERE shortlisted = true', ())
    return jsonify({
        'totalAdmins': total_admins['cnt'] if total_admins else 0,
        'totalCandidates': total_candidates['cnt'] if total_candidates else 0,
        'totalJobs': total_jobs['cnt'] if total_jobs else 0,
        'activeJobs': active_jobs['cnt'] if active_jobs else 0,
        'totalApplications': total_applications['cnt'] if total_applications else 0,
        'shortlistedApplications': shortlisted['cnt'] if shortlisted else 0,
    })


# ---------------------------------------------------------------------------
# Admins (HR users) — list/create/delete for Head of HR
# ---------------------------------------------------------------------------

@head_hr_bp.get('/admins')
@require_analytics_read
def list_admins():
    rows = db_all(
        '''SELECT hrid, full_name, email, company, created_at FROM hr_signup
           WHERE COALESCE(account_status, 'active') = 'active'
           ORDER BY created_at DESC''',
        (),
    )
    return jsonify({'admins': rows})


@head_hr_bp.post('/admins')
@authenticate_token
@require_head_hr
def create_admin():
    """Create a new HR/admin account (Head of HR only). Body: email, fullName, company, password."""
    if is_read_only(request.user):
        return jsonify({'error': 'Read-only access'}), 403
    data = request.get_json(force=True) or {}
    email = (data.get('email') or '').strip().lower()
    full_name = (data.get('fullName') or data.get('full_name') or '').strip()
    company = (data.get('company') or '').strip()
    password = (data.get('password') or '').strip()

    if not email:
        return jsonify({'error': 'Email is required'}), 400
    if not password or len(password) < 6:
        return jsonify({'error': 'Password is required and must be at least 6 characters'}), 400
    if not full_name:
        return jsonify({'error': 'Full name is required'}), 400
    if not company:
        return jsonify({'error': 'Company is required'}), 400

    existing = db_get('SELECT hrid FROM hr_signup WHERE LOWER(email) = ?', (email,))
    if existing:
        return jsonify({'error': 'An admin with this email already exists'}), 400

    try:
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        row = db_get('SELECT COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INT)), 0) AS maxn FROM hr_signup WHERE hrid ~ ?', ('^HRID[0-9]+$',))
        next_num = int(row['maxn']) + 1 if row and row.get('maxn') is not None else 1
        hrid = f"HRID{next_num:03d}"
        db_run(
            """
            INSERT INTO hr_signup (hrid, full_name, email, company, password, account_status)
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (hrid, full_name, email, company or '-', password_hash),
        )
        return jsonify({
            'message': 'Admin account created successfully',
            'admin': {'hrid': hrid, 'full_name': full_name, 'email': email, 'company': company or '-'},
        }), 201
    except Exception as e:
        print(f'[HEAD HR] Error creating admin: {e}')
        return jsonify({'error': 'Failed to create admin'}), 500


@head_hr_bp.route('/admins/<hrid>', methods=['PUT', 'DELETE', 'OPTIONS'])
@allow_options_no_auth
@authenticate_token
@require_head_hr
def update_or_delete_admin(hrid):
    """PUT: update admin. DELETE: remove admin. OPTIONS: CORS preflight."""
    if request.method == 'OPTIONS':
        return '', 204
    if is_read_only(request.user):
        return jsonify({'error': 'Read-only access'}), 403

    if request.method == 'DELETE':
        existing = db_get('SELECT hrid FROM hr_signup WHERE hrid = ?', (hrid,))
        if not existing:
            return jsonify({'error': 'Admin not found'}), 404
        try:
            db_run('DELETE FROM hr_signup WHERE hrid = ?', (hrid,))
            return jsonify({'message': f'Admin {hrid} deleted successfully'})
        except Exception as e:
            print(f'[HEAD HR] Error deleting admin {hrid}: {e}')
            return jsonify({'error': 'Failed to delete admin'}), 500

    # PUT — update
    existing = db_get(
        'SELECT hrid, full_name, email, company FROM hr_signup WHERE hrid = ?',
        (hrid,),
    )
    if not existing:
        return jsonify({'error': 'Admin not found'}), 404

    data = request.get_json(force=True) or {}
    full_name = (data.get('fullName') or data.get('full_name') or '').strip()
    company = (data.get('company') or '').strip()
    password = (data.get('password') or '').strip()

    if not full_name:
        return jsonify({'error': 'Full name is required'}), 400
    if not company:
        return jsonify({'error': 'Company is required'}), 400
    if password and len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    try:
        if password:
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            db_run(
                'UPDATE hr_signup SET full_name = ?, company = ?, password = ? WHERE hrid = ?',
                (full_name, company, password_hash, hrid),
            )
            try:
                db_run(
                    'UPDATE hr_auth SET full_name = ?, company = ?, password_hash = ? WHERE LOWER(email) = ?',
                    (full_name, company, password_hash, (existing.get('email') or '').lower()),
                )
            except Exception:
                pass
        else:
            db_run(
                'UPDATE hr_signup SET full_name = ?, company = ? WHERE hrid = ?',
                (full_name, company, hrid),
            )
            try:
                db_run(
                    'UPDATE hr_auth SET full_name = ?, company = ? WHERE LOWER(email) = ?',
                    (full_name, company, (existing.get('email') or '').lower()),
                )
            except Exception:
                pass

        return jsonify({
            'message': 'Admin updated successfully',
            'admin': {
                'hrid': hrid,
                'full_name': full_name,
                'email': existing.get('email'),
                'company': company,
            },
        })
    except Exception as e:
        print(f'[HEAD HR] Error updating admin {hrid}: {e}')
        return jsonify({'error': 'Failed to update admin'}), 500


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

@head_hr_bp.get('/candidates')
@require_analytics_read
def list_candidates():
    """Applicants who have applied to at least one job (matches Overview Candidates metric)."""
    rows = db_all(
        '''SELECT cs.cid, cs.name, cs.email, cs.created_at,
                  cp.full_name, cp.phone, cp.experience_level,
                  cp.current_location, cp.completed,
                  COUNT(a.id)::int AS application_count,
                  MAX(a.applied_at) AS last_applied_at,
                  STRING_AGG(DISTINCT j.title, ', ') AS jobs_applied
           FROM candidate_signup cs
           INNER JOIN applications a ON a.candidate_id = cs.cid
           LEFT JOIN candidate_profiles cp ON cp.candidate_id = cs.cid
           LEFT JOIN jobs j ON j.jdid = a.job_id
           GROUP BY cs.cid, cs.name, cs.email, cs.created_at,
                    cp.full_name, cp.phone, cp.experience_level,
                    cp.current_location, cp.completed
           ORDER BY MAX(a.applied_at) DESC NULLS LAST''',
        (),
    )
    return jsonify({'candidates': rows})


def _head_hr_profile_payload(cid):
    """Build full profile payload for a candidate (profile + education + certs + experiences)."""
    profile = db_get(
        '''
        SELECT cp.candidate_id, cp.full_name, cp.email, cp.phone,
               cp.experience_level, cp.serving_notice, cp.notice_period, cp.last_working_day,
               cp.linkedin_url, cp.portfolio_url, cp.current_location, cp.preferred_location,
               cp.completed, cp.updated_at,
               CASE WHEN cp.resume IS NOT NULL THEN 1 ELSE 0 END as has_resume,
               cs.name AS signup_name, cs.created_at AS signup_created_at
        FROM candidate_profiles cp
        LEFT JOIN candidate_signup cs ON cs.cid = cp.candidate_id
        WHERE cp.candidate_id = ?
        ''',
        (cid,),
    )
    if not profile:
        return None
    cgpa_col = '"cgpa/percentage"'  # PostgreSQL
    education = db_all(
        f'SELECT degree, institution, {cgpa_col} as cgpa, start_date, end_date FROM candidate_education WHERE candidate_id = ? ORDER BY degree',
        (cid,),
    )
    certifications = db_all(
        'SELECT certification, issuer, end_month FROM candidate_certifications WHERE candidate_id = ? ORDER BY certification',
        (cid,),
    )
    experiences = db_all(
        'SELECT company, role, start_date, end_date, present FROM candidate_experiences WHERE candidate_id = ? ORDER BY company',
        (cid,),
    )
    return {
        'candidate_id': cid,
        'fullName': profile.get('full_name') or profile.get('signup_name') or '',
        'email': profile.get('email') or '',
        'phone': profile.get('phone') or '',
        'experienceLevel': profile.get('experience_level') or '',
        'servingNotice': profile.get('serving_notice') or '',
        'noticePeriod': profile.get('notice_period') or '',
        'lastWorkingDay': profile.get('last_working_day') or '',
        'linkedinUrl': profile.get('linkedin_url') or '',
        'portfolioUrl': profile.get('portfolio_url') or '',
        'currentLocation': profile.get('current_location') or '',
        'preferredLocation': profile.get('preferred_location') or '',
        'completed': bool(profile.get('completed')),
        'resumeFileName': 'resume.pdf' if profile.get('has_resume') else '',
        'hasResume': bool(profile.get('has_resume')),
        'joinedAt': profile.get('signup_created_at'),
        'education': [
            {'degree': r.get('degree') or '', 'institution': r.get('institution') or '', 'cgpa': r.get('cgpa') or '', 'startMonth': r.get('start_date') or '', 'endMonth': r.get('end_date') or ''}
            for r in (education or [])
        ],
        'certifications': [
            {'certification': r.get('certification') or '', 'issuer': r.get('issuer') or '', 'endMonth': r.get('end_month') or ''}
            for r in (certifications or [])
        ],
        'experiences': [
            {'company': r.get('company') or '', 'role': r.get('role') or '', 'startMonth': r.get('start_date') or '', 'endMonth': r.get('end_date') or '', 'isCurrent': (r.get('present') or '').lower() == 'yes'}
            for r in (experiences or [])
        ],
    }


@head_hr_bp.route('/candidates/<cid>', methods=['GET', 'OPTIONS'])
@allow_options_no_auth
@require_analytics_read
def get_candidate(cid):
    """Return full candidate profile for Head HR detail view."""
    payload = _head_hr_profile_payload(cid)
    if not payload:
        signup = db_get('SELECT cid, name, email, created_at FROM candidate_signup WHERE cid = ?', (cid,))
        if not signup:
            return jsonify({'error': 'Candidate not found'}), 404
        return jsonify({
            'candidate_id': cid,
            'fullName': signup.get('name') or '',
            'email': signup.get('email') or '',
            'phone': '',
            'experienceLevel': '',
            'servingNotice': '',
            'noticePeriod': '',
            'lastWorkingDay': '',
            'linkedinUrl': '',
            'portfolioUrl': '',
            'currentLocation': '',
            'preferredLocation': '',
            'completed': False,
            'resumeFileName': '',
            'hasResume': False,
            'joinedAt': signup.get('created_at'),
            'education': [],
            'certifications': [],
            'experiences': [],
        })
    return jsonify(payload)


def _resume_bytes(data):
    if data is None:
        return None
    if isinstance(data, bytes):
        return data
    if isinstance(data, memoryview):
        return data.tobytes()
    if isinstance(data, bytearray):
        return bytes(data)
    try:
        return bytes(data)
    except (TypeError, ValueError):
        return None


@head_hr_bp.route('/candidates/<cid>/resume', methods=['GET', 'OPTIONS'])
@allow_options_no_auth
@require_analytics_read
def get_candidate_resume(cid):
    """Serve candidate resume PDF for Head HR."""
    from flask import Response
    profile = db_get('SELECT resume FROM candidate_profiles WHERE candidate_id = ?', (cid,))
    if not profile or not profile.get('resume'):
        return jsonify({'error': 'Resume not found'}), 404
    data = _resume_bytes(profile.get('resume'))
    if not data:
        return jsonify({'error': 'Invalid resume data'}), 500
    return Response(
        data,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'inline; filename=resume_{cid}.pdf',
            'Content-Type': 'application/pdf',
            'X-Content-Type-Options': 'nosniff',
        },
    )


@head_hr_bp.delete('/candidates/<cid>')
@authenticate_token
@require_head_hr
def delete_candidate(cid):
    existing = db_get('SELECT cid FROM candidate_signup WHERE cid = ?', (cid,))
    if not existing:
        return jsonify({'error': 'Candidate not found'}), 404
    try:
        db_run('DELETE FROM candidate_signup WHERE cid = ?', (cid,))
        return jsonify({'message': f'Candidate {cid} deleted successfully'})
    except Exception as e:
        print(f'[HEAD HR] Error deleting candidate {cid}: {e}')
        return jsonify({'error': 'Failed to delete candidate'}), 500


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@head_hr_bp.get('/jobs')
@require_analytics_read
def list_jobs():
    rows = db_all(
        '''SELECT j.jdid, j.title, j.company, j.location, j.salary,
                  j.experience, j.enabled, j.posted_on,
                  h.full_name AS posted_by_name, h.email AS posted_by_email
           FROM jobs j
           LEFT JOIN hr_signup h ON h.hrid = j.posted_by
           ORDER BY j.posted_on DESC''',
        (),
    )
    return jsonify({'jobs': rows})


@head_hr_bp.route('/jobs/<jdid>', methods=['GET', 'OPTIONS', 'DELETE'])
@allow_options_no_auth
@authenticate_token
def job_detail_or_delete(jdid):
    """GET: full job details. OPTIONS: CORS preflight. DELETE: remove job (HEAD_HR only)."""
    if request.method == 'OPTIONS':
        return '', 204
    if request.method == 'DELETE':
        from app.domains.identity.authorization.rbac import is_head_hr, is_read_only
        if is_read_only(request.user) or not is_head_hr(request.user):
            return jsonify({'error': 'Forbidden'}), 403
        existing = db_get('SELECT jdid FROM jobs WHERE jdid = ?', (jdid,))
        if not existing:
            return jsonify({'error': 'Job not found'}), 404
        try:
            cascade_delete_job(jdid)
            return jsonify({'message': f'Job {jdid} deleted successfully'})
        except Exception as e:
            print(f'[HEAD HR] Error deleting job {jdid}: {e}')
            return jsonify({'error': 'Failed to delete job'}), 500
    from app.domains.identity.authorization.rbac import has_permission
    if not has_permission(getattr(request, 'user', None), 'analytics:read'):
        return jsonify({'error': 'Forbidden'}), 403
    row = db_get(
        '''SELECT j.jdid, j.title, j.company, j.location, j.salary,
                  j.experience, j.description, j.enabled, j.posted_on, j.posted_by,
                  h.full_name AS posted_by_name, h.email AS posted_by_email
           FROM jobs j
           LEFT JOIN hr_signup h ON h.hrid = j.posted_by
           WHERE j.jdid = ?''',
        (jdid,),
    )
    if not row:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({
        'jdid': row['jdid'],
        'title': row.get('title'),
        'company': row.get('company'),
        'location': row.get('location'),
        'salary': row.get('salary'),
        'experience': row.get('experience'),
        'description': row.get('description') or '',
        'enabled': bool(row.get('enabled')),
        'posted_on': row.get('posted_on'),
        'posted_by': row.get('posted_by'),
        'posted_by_name': row.get('posted_by_name'),
        'posted_by_email': row.get('posted_by_email'),
    })


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@head_hr_bp.get('/applications')
@require_analytics_read
def list_applications():
    rows = db_all(
        '''SELECT a.id, a.candidate_id, a.job_id, a.status,
                  a.applied_at,
                  COALESCE(m.match_score, a.match_score) AS match_score,
                  a.shortlisted,
                  COALESCE(m.analysis_toon, a.ats_analysis) AS ats_analysis,
                  cs.name AS candidate_name, cs.email AS candidate_email,
                  j.title AS job_title, j.company AS job_company,
                  h.full_name AS hr_name
           FROM applications a
           LEFT JOIN matches m ON m.id = a.latest_match_id
           LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
           LEFT JOIN jobs j ON j.jdid = a.job_id
           LEFT JOIN hr_signup h ON h.hrid = j.posted_by
           ORDER BY a.applied_at DESC''',
        (),
    )
    applications = []
    for row in rows or []:
        item = dict(row)
        ats_raw = item.pop('ats_analysis', None)
        ats_analysis = toon_loads_flex(ats_raw) if ats_raw else None
        stored = item.get('match_score')
        try:
            stored_f = float(stored) if stored is not None else None
        except (TypeError, ValueError):
            stored_f = None
        if (ats_analysis):
            recon = sync_application_match_score(item.get('id'), ats_analysis, stored_f, persist=True)
            if recon.get('match_score') is not None:
                item['match_score'] = float(recon['match_score'])
            if recon.get('verdict'):
                item['verdict'] = recon['verdict']
            # Keep analysis available so clients can re-derive display score if needed
            item['ats_analysis'] = recon.get('ats_analysis') or ats_analysis
        elif stored_f is not None:
            item['match_score'] = stored_f
        applications.append(item)
    return jsonify({'applications': applications})


@head_hr_bp.route('/applications/<int:app_id>', methods=['OPTIONS'])
def options_application(app_id):
    """Allow CORS preflight for GET /applications/<id> (no auth on preflight)."""
    return '', 204


@head_hr_bp.get('/applications/<int:app_id>')
@require_analytics_read
def get_application(app_id):
    """Return one application with full ATS analysis for Head HR detail view."""
    row = db_get(
        '''SELECT a.id, a.candidate_id, a.job_id, a.status,
                  a.applied_at,
                  COALESCE(m.match_score, a.match_score) AS match_score,
                  a.shortlisted,
                  COALESCE(m.rationale, a.ats_reasoning) AS ats_reasoning,
                  COALESCE(m.analysis_toon, a.ats_analysis) AS ats_analysis,
                  cs.name AS candidate_name, cs.email AS candidate_email,
                  j.title AS job_title, j.company AS job_company,
                  h.full_name AS hr_name
           FROM applications a
           LEFT JOIN matches m ON m.id = a.latest_match_id
           LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
           LEFT JOIN jobs j ON j.jdid = a.job_id
           LEFT JOIN hr_signup h ON h.hrid = j.posted_by
           WHERE a.id = ?''',
        (app_id,),
    )
    if not row:
        return jsonify({'error': 'Application not found'}), 404
    ats_raw = row.get('ats_analysis')
    ats_analysis = toon_loads_flex(ats_raw) if ats_raw else None
    try:
        stored_f = float(row['match_score']) if row.get('match_score') is not None else None
    except (TypeError, ValueError):
        stored_f = None
    verdict = None
    if ats_analysis:
        recon = sync_application_match_score(row['id'], ats_analysis, stored_f, persist=True)
        if recon.get('match_score') is not None:
            stored_f = float(recon['match_score'])
        if recon.get('ats_analysis') is not None:
            ats_analysis = recon['ats_analysis']
        verdict = recon.get('verdict')
    payload = {
        'id': row['id'],
        'candidate_id': row['candidate_id'],
        'job_id': row['job_id'],
        'status': row['status'],
        'applied_at': row['applied_at'],
        'match_score': stored_f,
        'shortlisted': bool(row.get('shortlisted')),
        'ats_reasoning': row.get('ats_reasoning'),
        'ats_analysis': ats_analysis,
        'candidate_name': row.get('candidate_name'),
        'candidate_email': row.get('candidate_email'),
        'job_title': row.get('job_title'),
        'job_company': row.get('job_company'),
        'hr_name': row.get('hr_name'),
        'verdict': verdict,
    }
    return jsonify(payload)
