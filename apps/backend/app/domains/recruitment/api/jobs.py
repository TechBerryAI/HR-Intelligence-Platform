import json
import re
from datetime import datetime
from typing import Optional
from flask import Blueprint, request, jsonify
from app.database.connection.db import db_all, db_get, db_run, BACKEND, TRUE_SQL, FALSE_SQL
from app.api.middleware.auth import authenticate_token, require_recruiter, optional_authenticate_token
from app.domains.identity.authorization.rbac import (
    can_access_job,
    can_modify_job,
    is_read_only,
    get_user_id,
)
from app.ai.toon.runtime import toon_loads_flex
from app.domains.candidate.services.profile_service import (
    link_parsed_resume,
    normalize_email,
    save_candidate_profile,
    upsert_passwordless_candidate,
    validate_public_apply_payload,
)
from app.domains.recruitment.api.applications import (
    _extract_ats_result,
    _jd_toon_from_job_row,
    _persist_application_atomic,
)
from app.domains.recruitment.services.job_delete import cascade_delete_job
from app.domains.recruitment.services.ats_service import match_candidate_to_job, sync_application_match_score
from app.domains.identity.services.organizations import (
    attach_organization_id,
    find_organization_by_slug,
    get_organization,
    require_organization_id,
)
from app.domains.integrations.events import emit_job_closed, emit_job_created, emit_job_updated
from app.core.timing import timing

jobs_bp = Blueprint('jobs', __name__)


def _jobs_for_organization(org_id: str) -> list:
    """All jobs belonging to an organization."""
    return db_all(
        '''
        SELECT j.*, hs.company as company_name
        FROM jobs j
        LEFT JOIN hr_signup hs ON j.posted_by = hs.hrid
        WHERE j.organization_id = ?
        ORDER BY j.posted_on DESC
        ''',
        (org_id,),
    )


def _job_enabled_flag(job: dict) -> bool:
    """NULL enabled means visible/active (matches public SQL filter)."""
    val = job.get('enabled')
    if val is None:
        return True
    return bool(val)


def _get_job_for_user(job_id, user, require_write=False):
    job = db_get('SELECT * FROM jobs WHERE jdid = ?', (job_id,))
    if not job:
        return None
    org_id = job.get('organization_id')
    posted_by = job.get('posted_by')
    if require_write:
        if can_modify_job(user, posted_by=posted_by, organization_id=org_id):
            return job
        return None
    if user and get_user_id(user):
        if not can_access_job(user, posted_by=posted_by, organization_id=org_id):
            return None
    return job


def _public_org_from_request():
    """Resolve company slug from query (?company=)."""
    slug = (request.args.get('company') or request.args.get('slug') or '').strip().lower()
    return find_organization_by_slug(slug) if slug else None


def _job_matches_public_org(job: dict, org: dict | None) -> bool:
    if not job or not org:
        return False
    return str(job.get('organization_id') or '') == str(org.get('id') or '')


def _normalize_keywords(value) -> Optional[str]:
    """Normalize keywords to a comma-separated string (or None if empty)."""
    if value is None:
        return None
    if isinstance(value, list):
        parts = [str(v).strip() for v in value if v is not None and str(v).strip()]
    else:
        raw = str(value).strip()
        if not raw:
            return None
        if '|' in raw:
            parts = [p.strip() for p in raw.split('|') if p.strip()]
        else:
            parts = [p.strip() for p in raw.split(',') if p.strip()]
    if not parts:
        return None
    # Dedupe case-insensitively, preserve first-seen casing
    seen = set()
    out = []
    for p in parts:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return ', '.join(out)


def _serialize_job(job: dict, company_fallback: str = None) -> dict:
    return {
        'id': job['jdid'],
        'title': job['title'],
        'company': job.get('company') or company_fallback or job.get('company_name'),
        'location': job['location'],
        'salary': job['salary'],
        'experience': job.get('experience'),
        'description': job['description'],
        'keywords': job.get('keywords') or '',
        'enabled': _job_enabled_flag(job),
        'postedOn': job['posted_on'],
        'parsedJdId': job.get('parsed_jd_id'),
    }


def _send_notification(hr_action, candidate_name, candidate_email, job_title, company_name, application_id, timestamp):
    """Lazy import so jobs_bp loads even if notification service or its deps (flask_mail, etc.) fail."""
    from app.domains.recruitment.services.notifications import send_and_get_output
    return send_and_get_output(
        hr_action=hr_action,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        job_title=job_title,
        company_name=company_name,
        application_id=application_id,
        timestamp=timestamp,
    )


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


def generate_jdid_from_title(title):
    """
    Generate jdid from job title.
    Pattern: First letter of each word + 3-digit sequence number
    Examples:
    - "data analyst" -> "DA001"
    - "software developer" -> "SD001"
    - "engineer" -> "E001"
    """
    if not title:
        return "JD001"
    
    # Extract first letter of each word (uppercase)
    words = re.findall(r'\b\w', title.upper())
    if not words:
        prefix = "JD"
    else:
        # Take first letter of each word, up to reasonable length
        prefix = ''.join(words[:5])  # Max 5 letters for prefix
    
    # Find the last jdid with this prefix (e.g. DA001, SD002)
    if BACKEND == "postgresql":
        # PostgreSQL: use SUBSTRING and ~ for numeric suffix
        existing = db_get(
            '''
            SELECT jdid FROM jobs
            WHERE jdid LIKE ?
            ORDER BY
              CASE WHEN SUBSTRING(jdid FROM LENGTH(?) + 1) ~ '^[0-9]+$'
                THEN CAST(SUBSTRING(jdid FROM LENGTH(?) + 1) AS INT)
                ELSE 0
              END DESC NULLS LAST,
              jdid DESC
            LIMIT 1
            ''',
            (f'{prefix}%', prefix, prefix)
        )
    else:
        existing = db_get(
            '''
            SELECT TOP 1 jdid
            FROM jobs
            WHERE jdid LIKE ?
            ORDER BY
              CASE
                WHEN ISNUMERIC(SUBSTRING(jdid, LEN(?) + 1, 10)) = 1
                THEN CAST(SUBSTRING(jdid, LEN(?) + 1, 10) AS INT)
                ELSE 0
              END DESC,
              jdid DESC
            ''',
            (f'{prefix}%', prefix, prefix)
        )
    
    if existing and existing.get('jdid'):
        try:
            # Extract number part after prefix
            existing_jdid = str(existing['jdid'])
            if len(existing_jdid) > len(prefix):
                num_part = existing_jdid[len(prefix):]
                # Extract only numeric part (in case of old INT jdid)
                num_part = ''.join(filter(str.isdigit, num_part))
                if num_part:
                    next_num = int(num_part) + 1
                else:
                    next_num = 1
            else:
                next_num = 1
        except (ValueError, IndexError, TypeError):
            next_num = 1
    else:
        next_num = 1
    
    # Format: PREFIX + 3-digit number (e.g., DA001, SD001)
    return f"{prefix}{next_num:03d}"


@jobs_bp.get('/')
@optional_authenticate_token
def get_jobs_public():
    """
    Public job board: enabled jobs for one company slug (?company=slug).
    Unscoped requests are rejected (no global scrape).
    """
    try:
        org = _public_org_from_request()
        if not org:
            return jsonify({
                'error': 'Company slug required',
                'hint': 'Pass ?company=<slug> or browse GET /api/companies',
            }), 400
        jobs = db_all(
            '''
            SELECT j.*, hs.company as company_name
            FROM jobs j
            LEFT JOIN hr_signup hs ON j.posted_by = hs.hrid
            WHERE j.organization_id = ?
              AND (j.enabled = ''' + TRUE_SQL + ''' OR j.enabled IS NULL)
            ORDER BY j.posted_on DESC
            ''',
            (str(org['id']),),
        )
        formatted = [_serialize_job(j) for j in jobs]
        return jsonify(formatted)
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.get('/all')
@authenticate_token
@require_recruiter
def get_jobs_all():
    """Staff job list: scoped to caller's organization."""
    try:
        org_id, err = require_organization_id(request.user)
        if err:
            return err
        jobs = _jobs_for_organization(org_id)
        formatted = [_serialize_job(j) for j in jobs]
        return jsonify(formatted)
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.get('/<string:job_id>')
@optional_authenticate_token
def get_job(job_id: str):
    """Get one job. Staff: same org only. Public: enabled + matching ?company=slug."""
    try:
        job = db_get(
            '''
            SELECT j.*, hs.company as company_name
            FROM jobs j
            LEFT JOIN hr_signup hs ON j.posted_by = hs.hrid
            WHERE j.jdid = ?
            ''', (job_id,)
        )
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        user = getattr(request, 'user', None)
        if user and get_user_id(user):
            if not can_access_job(
                user,
                posted_by=job.get('posted_by'),
                organization_id=job.get('organization_id'),
            ):
                return jsonify({'error': 'Job not found or access denied'}), 404
        else:
            org = _public_org_from_request()
            if not org or not _job_matches_public_org(job, org):
                return jsonify({'error': 'Job not found'}), 404
            if not job.get('enabled') and job.get('enabled') is not None:
                return jsonify({'error': 'Job not found'}), 404
        return jsonify(_serialize_job(job))
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.get('/<string:job_id>/applications')
@authenticate_token
@require_recruiter
def get_job_applications(job_id: str):
    try:
        # Verify job belongs to HR user
        job = _get_job_for_user(job_id, request.user, require_write=False)
        if not job:
            # Return 200 with empty list so UI shows "No candidates" instead of errors; avoids 404 in terminal
            return jsonify({'applications': []}), 200

        # Get applications with candidate details (ATS scores from matches via latest_match_id)
        applications = db_all(
            '''
            SELECT 
                a.id,
                a.candidate_id,
                a.job_id,
                a.status,
                a.applied_at,
                COALESCE(m.matching_percentage, a.matching_percentage) AS matching_percentage,
                COALESCE(m.match_score, a.match_score) AS match_score,
                a.shortlisted,
                COALESCE(m.rationale, a.ats_reasoning) AS ats_reasoning,
                COALESCE(m.analysis_toon, a.ats_analysis) AS ats_analysis,
                cp.full_name,
                cp.email,
                cp.phone,
                cp.current_location,
                cp.preferred_location,
                cp.experience_level,
                cp.serving_notice,
                cp.notice_period,
                cp.last_working_day,
                cp.linkedin_url,
                cp.portfolio_url,
                CASE
                    WHEN cp.resume IS NOT NULL OR cp.resume_raw_file_id IS NOT NULL THEN 1
                    ELSE 0
                END as has_resume,
                cs.name as candidate_name
            FROM applications a
            INNER JOIN candidate_profiles cp ON a.candidate_id = cp.candidate_id
            LEFT JOIN candidates cs ON a.candidate_id = cs.cid
            LEFT JOIN matches m ON m.id = a.latest_match_id
            WHERE a.job_id = ?
            ORDER BY COALESCE(m.matching_percentage, a.matching_percentage) DESC NULLS LAST,
                     a.applied_at DESC
            ''',
            (job_id,)
        )
        
        # Get related data (education, experiences, certifications)
        formatted_apps = []
        for app in applications:
            candidate_id = app['candidate_id']
            
            # Get education
            _cgpa_col = '"cgpa/percentage"' if BACKEND == "postgresql" else "[cgpa/percentage]"
            education = db_all(
                'SELECT degree, institution, ' + _cgpa_col + ' as cgpa, start_date, end_date FROM candidate_education WHERE candidate_id = ?',
                (candidate_id,)
            )
            
            # Get experiences
            experiences = db_all(
                'SELECT company, role, start_date, end_date, present FROM candidate_experiences WHERE candidate_id = ?',
                (candidate_id,)
            )
            
            # Get certifications
            certifications = db_all(
                'SELECT certification, issuer, end_month FROM candidate_certifications WHERE candidate_id = ?',
                (candidate_id,)
            )
            
            # Prefer ATS match_score when present; fallback to matching_percentage
            match_score = app.get('match_score')
            if match_score is not None:
                try:
                    match_score = float(match_score)
                except (ValueError, TypeError):
                    match_score = None
            matching_pct = app.get('matching_percentage')
            if matching_pct is None:
                matching_pct = 0
            else:
                try:
                    matching_pct = float(matching_pct)
                    if matching_pct < 0:
                        matching_pct = 0
                    elif matching_pct > 100:
                        matching_pct = 100
                except (ValueError, TypeError):
                    matching_pct = 0

            ats_analysis_raw = app.get('ats_analysis')
            ats_analysis = toon_loads_flex(ats_analysis_raw) if ats_analysis_raw else None
            if ats_analysis:
                recon = sync_application_match_score(app.get('id'), ats_analysis, match_score, persist=True)
                if recon.get('match_score') is not None:
                    match_score = float(recon['match_score'])
                    matching_pct = match_score
                if recon.get('ats_analysis') is not None:
                    ats_analysis = recon['ats_analysis']
            score_display = match_score if match_score is not None else matching_pct

            formatted_apps.append({
                'id': app['id'],
                'candidateId': app['candidate_id'],
                'jobId': app['job_id'],
                'status': app['status'],
                'appliedAt': app['applied_at'],
                'matchScore': score_display,
                'score': score_display,
                'shortlisted': bool(app.get('shortlisted')),
                'atsReasoning': app.get('ats_reasoning'),
                'atsAnalysis': ats_analysis,
                'fullName': app.get('full_name') or app.get('candidate_name') or 'Unknown',
                'name': app.get('full_name') or app.get('candidate_name') or 'Unknown',
                'email': app.get('email'),
                'phone': app.get('phone'),
                'currentLocation': app.get('current_location'),
                'preferredLocation': app.get('preferred_location'),
                'experienceLevel': app.get('experience_level'),
                'servingNotice': app.get('serving_notice'),
                'noticePeriod': app.get('notice_period'),
                'lastWorkingDay': app.get('last_working_day'),
                'linkedinUrl': app.get('linkedin_url'),
                'portfolioUrl': app.get('portfolio_url'),
                'resumeFileName': 'resume.pdf' if app.get('has_resume') else None,
                'resumeUrl': f'/api/jobs/{job_id}/applications/{candidate_id}/resume' if app.get('has_resume') else None,
                'education': [
                    {
                        'degree': e.get('degree') or '',
                        'institution': e.get('institution') or '',
                        'cgpa': e.get('cgpa') or '',
                        'startMonth': e.get('start_date') or '',
                        'endMonth': e.get('end_date') or '',
                    }
                    for e in (education or [])
                ],
                'experiences': [
                    {
                        'company': e.get('company') or '',
                        'role': e.get('role') or '',
                        'startMonth': e.get('start_date') or '',
                        'endMonth': e.get('end_date') or '',
                        'isCurrent': (e.get('present') or '').lower() == 'yes',
                    }
                    for e in (experiences or [])
                ],
                'certifications': [
                    {
                        'certification': c.get('certification') or '',
                        'issuer': c.get('issuer') or '',
                        'endMonth': c.get('end_month') or '',
                    }
                    for c in (certifications or [])
                ],
            })
        
        return jsonify({'applications': formatted_apps})
    except Exception as e:
        print(f"Error in get_job_applications: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.get('/<string:job_id>/applications/<string:candidate_id>/resume')
@authenticate_token
@require_recruiter
def get_candidate_resume(job_id: str, candidate_id: str):
    """Download candidate resume for HR"""
    try:
        # Verify job belongs to HR user
        job = _get_job_for_user(job_id, request.user, require_write=False)
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404
        
        # Verify candidate has applied to this job
        application = db_get('SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?', (job_id, candidate_id))
        if not application:
            return jsonify({'error': 'Application not found'}), 404
        
        # Get resume (prefer media via resume_raw_file_id, fallback BYTEA)
        profile = db_get(
            '''
            SELECT resume, resume_raw_file_id
            FROM candidate_profiles
            WHERE candidate_id = ?
            ''',
            (candidate_id,)
        )
        if not profile:
            return jsonify({'error': 'Resume not found'}), 404

        from flask import Response
        from app.domains.recruitment.services.parsing_storage import load_raw_file_bytes

        resume_data = None
        raw_id = profile.get('resume_raw_file_id')
        if raw_id:
            resume_data = load_raw_file_bytes(str(raw_id))
        if not resume_data:
            resume_data = _resume_bytes(profile.get('resume'))
        if resume_data:
            return Response(
                resume_data,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'inline; filename=resume_{candidate_id}.pdf',
                    'Content-Type': 'application/pdf',
                    'X-Content-Type-Options': 'nosniff',
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )
        return jsonify({'error': 'Resume not found'}), 404
    except Exception as e:
        print(f"Error in get_candidate_resume: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.post('/<string:job_id>/applications/<string:candidate_id>/viewed')
@authenticate_token
@require_recruiter
def record_profile_viewed(job_id: str, candidate_id: str):
    """Record that HR viewed this candidate's profile for this job. Sends email and updates status."""
    try:
        job = _get_job_for_user(job_id, request.user, require_write=True)
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404
        app = db_get(
            'SELECT id, status, shortlisted FROM applications WHERE job_id = ? AND candidate_id = ?',
            (job_id, candidate_id)
        )
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        current_status = (app.get('status') or '').lower()
        is_shortlisted = app.get('shortlisted') in (True, 1, 't', 'true', '1')
        if current_status == 'shortlisted' or current_status == 'rejected' or is_shortlisted:
            return jsonify({
                'status': 'ok',
                'profile_update': {
                    'application_id': str(app['id']),
                    'status': 'Shortlisted' if (current_status == 'shortlisted' or is_shortlisted) else 'Rejected',
                    'updated_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'unchanged': True,
                }
            }), 200
        profile = db_get('SELECT full_name, email FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
        signup = db_get('SELECT email FROM candidates WHERE cid = ?', (candidate_id,))
        app['full_name'] = (profile or {}).get('full_name') or ''
        app['email'] = (profile or {}).get('email') or (signup or {}).get('email') or ''
        ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        status_db = 'profile_viewed'
        if app['email']:
            out = _send_notification(
                hr_action='PROFILE_VIEWED',
                candidate_name=app.get('full_name') or '',
                candidate_email=app['email'],
                job_title=job.get('title') or '',
                company_name=job.get('company') or '',
                application_id=app['id'],
                timestamp=ts,
            )
            status_db = out['profile_update']['status_db']
        db_run(
            'UPDATE applications SET status = ? WHERE id = ?',
            (status_db, app['id'])
        )
        return jsonify({'status': 'ok', 'profile_update': {'application_id': str(app['id']), 'status': 'Profile Viewed', 'updated_at': ts}}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error in record_profile_viewed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.patch('/<string:job_id>/applications/<string:candidate_id>/status')
@authenticate_token
@require_recruiter
def update_application_status(job_id: str, candidate_id: str):
    """Shortlist or reject candidate. Body: { "action": "shortlist" | "reject" }.

    Shortlist: send SHORTLISTED email + interview scheduling.
    Reject: update DB only (no email) so candidates stay available for future roles.
    """
    try:
        data = request.get_json(force=True) or {}
        action = (data.get('action') or '').strip().lower()
        if action not in ('shortlist', 'reject'):
            return jsonify({'error': 'action must be "shortlist" or "reject"'}), 400
        job = _get_job_for_user(job_id, request.user, require_write=True)
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404
        app = db_get('SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?', (job_id, candidate_id))
        if not app:
            return jsonify({'error': 'Application not found'}), 404

        from app.common.application_status import STATUS_REJECTED

        if action == 'reject':
            _sl_val = False if BACKEND == 'postgresql' else 0
            db_run(
                'UPDATE applications SET status = ?, shortlisted = ? WHERE id = ?',
                (STATUS_REJECTED, _sl_val, app['id'])
            )
            return jsonify({
                'status': 'ok',
                'profile_update': {
                    'status': 'rejected',
                    'status_db': STATUS_REJECTED,
                    'status_label': 'Not Shortlisted',
                },
            }), 200

        profile = db_get('SELECT full_name, email FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
        signup = db_get('SELECT email FROM candidates WHERE cid = ?', (candidate_id,))
        app['full_name'] = (profile or {}).get('full_name') or ''
        app['email'] = (profile or {}).get('email') or (signup or {}).get('email') or ''
        if not app['email']:
            return jsonify({'error': 'Candidate email not found; cannot send notification'}), 400
        ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        out = _send_notification(
            hr_action='SHORTLISTED',
            candidate_name=app.get('full_name') or '',
            candidate_email=app.get('email') or '',
            job_title=job.get('title') or '',
            company_name=job.get('company') or '',
            application_id=app['id'],
            timestamp=ts,
        )
        _sl_val = True if BACKEND == 'postgresql' else 1
        db_run(
            'UPDATE applications SET status = ?, shortlisted = ? WHERE id = ?',
            (out['profile_update']['status_db'], _sl_val, app['id'])
        )
        from app.domains.recruitment.services.interview_trigger import trigger_interview_scheduling
        trigger_interview_scheduling(app['id'], recruiter_hrid=get_user_id(request.user))
        return jsonify({'status': 'ok', 'profile_update': out['profile_update']}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error in update_application_status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.post('/')
@authenticate_token
@require_recruiter
def create_job():
    try:
        if is_read_only(request.user):
            return jsonify({'error': 'Read-only access'}), 403
        print("CREATE JOB ENDPOINT CALLED")
        print(f"Request method: {request.method}")
        print(f"Request URL: {request.url}")
        print(f"Headers: {dict(request.headers)}")
        data = request.get_json(force=True) or {}
        print(f"Received data: {data}")
        print(f"User from token: {request.user}")
        title = (data.get('title') or '').strip()
        company = (data.get('company') or '').strip()
        location = (data.get('location') or '').strip()
        salary = (data.get('salary') or '').strip() or None
        experience = data.get('experience') or None
        if experience:
            experience = str(experience).strip() or None
        
        # Support legacy format: if experienceFrom/experienceTo provided, combine them
        if not experience:
            experience_from = data.get('experienceFrom')
            experience_to = data.get('experienceTo')
            # Handle string values
            if isinstance(experience_from, str):
                try:
                    experience_from = int(experience_from) if experience_from.strip() else None
                except (ValueError, AttributeError):
                    experience_from = None
            if isinstance(experience_to, str):
                try:
                    experience_to = int(experience_to) if experience_to.strip() else None
                except (ValueError, AttributeError):
                    experience_to = None
            
            if experience_from is not None or experience_to is not None:
                if experience_from is not None and experience_to is not None:
                    experience = f"{experience_from}-{experience_to} years"
                elif experience_from is not None:
                    experience = f"{experience_from}+ years"
                elif experience_to is not None:
                    experience = f"Up to {experience_to} years"
        
        description = (data.get('description') or '').strip()
        keywords = _normalize_keywords(data.get('keywords'))
        parsed_jd_id = (data.get('parsedJdId') or data.get('parsed_jd_id') or '').strip() or None

        def _as_skill_list(val):
            if isinstance(val, list):
                return [str(s).strip() for s in val if str(s or '').strip()]
            if isinstance(val, str) and val.strip():
                return [s.strip() for s in val.split(',') if s.strip()]
            return []

        mandatory_skills = _as_skill_list(
            data.get('mandatorySkills') or data.get('mandatory_skills')
        )
        preferred_skills = _as_skill_list(
            data.get('preferredSkills') or data.get('preferred_skills')
        )
        
        # Company + org always taken from the HR account
        hr_id = get_user_id(request.user)
        org_id, err = require_organization_id(request.user)
        if err:
            return err
        org = get_organization(org_id)
        company = ((org or {}).get('name') or '').strip()
        if hr_id and not company:
            hr_profile = db_get(
                'SELECT company, organization_id FROM hr_signup WHERE hrid = ?',
                (hr_id,),
            )
            if hr_profile and (hr_profile.get('company') or '').strip():
                company = (hr_profile.get('company') or '').strip()
        
        if not title or not company or not location or not description:
            missing_fields = []
            if not title: missing_fields.append('title')
            if not company: missing_fields.append('company')
            if not location: missing_fields.append('location')
            if not description: missing_fields.append('description')
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        # Ensure hrId exists
        hr_id = get_user_id(request.user)
        if not hr_id:
            return jsonify({'error': 'Invalid HR user. Please log in again.'}), 401
        
        # Generate jdid from job title
        jdid = generate_jdid_from_title(title)
        print(f"Generated jdid: {jdid} from title: {title}")
        
        print(f"Prepared job data: jdid={jdid}, title={title}, company={company}, location={location}, hr_id={hr_id}")
        print("Executing INSERT query...")
        
        _enabled_val = True if BACKEND == 'postgresql' else 1
        result = db_run(
            '''
            INSERT INTO jobs (jdid, title, company, location, salary, experience, description, keywords, posted_by, enabled, parsed_jd_id, organization_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (jdid, title, company, location, salary, experience, description, keywords, hr_id, _enabled_val, parsed_jd_id, org_id)
        )
        print(f"INSERT result: {result}")
        
        print("Fetching created job...")
        job = db_get('SELECT * FROM jobs WHERE jdid = ?', (jdid,))
        print(f"Retrieved job: {job}")
        
        if not job:
            print("ERROR: Job created but could not be retrieved")
            return jsonify({'error': 'Job created but could not be retrieved'}), 500

        if not job.get('organization_id'):
            attach_organization_id('jobs', 'jdid', jdid, org_id)
            job = db_get('SELECT * FROM jobs WHERE jdid = ?', (jdid,)) or job

        if parsed_jd_id:
            try:
                db_run('UPDATE parsed_jds SET job_id = ? WHERE id = ?', (jdid, parsed_jd_id))
                # Persist recruiter-edited skill tiers into linked TOON (ATS source of truth)
                if mandatory_skills or preferred_skills:
                    from app.ai.toon.runtime import toon_dumps, toon_loads_flex

                    row = db_get('SELECT toon FROM parsed_jds WHERE id = ?', (parsed_jd_id,))
                    if row and row.get('toon'):
                        toon = toon_loads_flex(row['toon'])
                        if isinstance(toon, dict):
                            if mandatory_skills:
                                toon['mandatory_skills'] = mandatory_skills
                            if preferred_skills:
                                toon['preferred_skills'] = preferred_skills
                            if mandatory_skills or preferred_skills:
                                combined = list(dict.fromkeys(
                                    (mandatory_skills or []) + (preferred_skills or [])
                                    + (toon.get('skills') if isinstance(toon.get('skills'), list) else [])
                                ))
                                toon['skills'] = combined
                            db_run(
                                'UPDATE parsed_jds SET toon = ? WHERE id = ?',
                                (toon_dumps(toon), parsed_jd_id),
                            )
            except Exception as link_err:
                print(f"[jobs] parsed_jd link warning: {link_err}")
        
        print("Job created successfully!")
        print("=" * 50)

        emit_job_created(job, request.user)

        return jsonify(_serialize_job(job)), 201
    except Exception as e:
        import traceback
        error_msg = str(e)
        print("=" * 50)
        print("ERROR IN CREATE JOB:")
        print(f"Error message: {error_msg}")
        traceback.print_exc()  # Print full traceback for debugging
        print("=" * 50)
        if 'FOREIGN KEY' in error_msg.upper():
            return jsonify({'error': 'Invalid HR user. Please log in again.'}), 400
        return jsonify({'error': f'Internal server error: {error_msg}'}), 500


@jobs_bp.put('/<string:job_id>')
@authenticate_token
@require_recruiter
def update_job(job_id: str):
    try:
        data = request.get_json(force=True)
        title = (data.get('title') or '').strip()
        location = (data.get('location') or '').strip()
        salary = (data.get('salary') or '').strip() or None
        experience = data.get('experience') or None
        if experience:
            experience = str(experience).strip() or None
        
        # Support legacy format: if experienceFrom/experienceTo provided, combine them
        if not experience:
            experience_from = data.get('experienceFrom')
            experience_to = data.get('experienceTo')
            # Handle string values
            if isinstance(experience_from, str):
                try:
                    experience_from = int(experience_from) if experience_from.strip() else None
                except (ValueError, AttributeError):
                    experience_from = None
            if isinstance(experience_to, str):
                try:
                    experience_to = int(experience_to) if experience_to.strip() else None
                except (ValueError, AttributeError):
                    experience_to = None
            
            if experience_from is not None or experience_to is not None:
                if experience_from is not None and experience_to is not None:
                    experience = f"{experience_from}-{experience_to} years"
                elif experience_from is not None:
                    experience = f"{experience_from}+ years"
                elif experience_to is not None:
                    experience = f"Up to {experience_to} years"
        description = (data.get('description') or '').strip()

        job = _get_job_for_user(job_id, request.user, require_write=True)
        if not job:
            return jsonify({'error': 'Job not found or access denied'}), 404

        if 'keywords' in data:
            keywords = _normalize_keywords(data.get('keywords'))
        else:
            keywords = job.get('keywords')

        # Determine if jdid needs to be regenerated
        # Regenerate if title, experience, or salary changed
        old_title = (job.get('title') or '').strip()
        old_experience = (job.get('experience') or '').strip()
        old_salary = (job.get('salary') or '').strip() or None
        new_title = title or old_title
        new_experience = experience or old_experience
        new_salary = salary if salary is not None else old_salary
        
        should_regenerate_jdid = (
            (title and title.strip() and title.strip().upper() != old_title.upper()) or
            (experience and experience.strip() != old_experience) or
            (salary is not None and salary != old_salary)
        )
        
        new_jdid = job_id  # Keep same jdid by default
        
        if should_regenerate_jdid:
            # Generate new jdid from title
            new_jdid = generate_jdid_from_title(new_title)
            print(f"Regenerating jdid: {job_id} -> {new_jdid} (title/experience/salary changed)")
            
            # If jdid changed, update foreign keys in other tables
            if new_jdid != job_id:
                # Update applications table
                db_run('UPDATE applications SET job_id = ? WHERE job_id = ?', (new_jdid, job_id))
                db_run('UPDATE matches SET job_id = ? WHERE job_id = ?', (new_jdid, job_id))
                db_run('UPDATE parsed_jds SET job_id = ? WHERE job_id = ?', (new_jdid, job_id))
                db_run(
                    'UPDATE external_jobs SET job_id = ? WHERE job_id = ?',
                    (new_jdid, job_id),
                )

        # Update job with new jdid if it changed
        db_run(
            '''
            UPDATE jobs SET
              jdid = ?,
              title = COALESCE(?, title),
              location = COALESCE(?, location),
              salary = ?,
              experience = ?,
              description = COALESCE(?, description),
              keywords = ?
            WHERE jdid = ?
            ''',
            (new_jdid, title, location, salary, experience, description, keywords, job_id)
        )
        updated = db_get('SELECT * FROM jobs WHERE jdid = ?', (new_jdid,))
        if updated:
            emit_job_updated(updated, request.user)
        return jsonify(_serialize_job(updated))
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.patch('/<string:job_id>/enabled')
@authenticate_token
@require_recruiter
def toggle_job(job_id: str):
    try:
        data = request.get_json(force=True)
        enabled = bool(data.get('enabled'))
        job = _get_job_for_user(job_id, request.user, require_write=True)
        if not job:
            return jsonify({'error': 'Job not found or you do not have permission to update this job'}), 403
        _enabled = (True, False) if BACKEND == 'postgresql' else (1, 0)
        db_run('UPDATE jobs SET enabled = ? WHERE jdid = ?', (_enabled[0] if enabled else _enabled[1], job_id))
        if not enabled:
            emit_job_closed(job, job_id=job_id, user=request.user)
        return jsonify({'message': 'Job status updated', 'enabled': enabled})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@jobs_bp.delete('/<string:job_id>')
@authenticate_token
@require_recruiter
def delete_job(job_id: str):
    try:
        job = _get_job_for_user(job_id, request.user, require_write=True)
        if not job:
            return jsonify({'error': 'Job not found or you do not have permission to delete this job'}), 403
        emit_job_closed(job, job_id=job_id, user=request.user)
        # Cascade applications/matches first — FK is NO ACTION on jobs
        cascade_delete_job(job_id)
        return jsonify({'message': 'Job deleted successfully'})
    except Exception as e:
        print(f'[JOBS] Error deleting job {job_id}: {e}')
        return jsonify({'error': 'Internal server error'}), 500


def _parse_json_field(raw, default=None):
    if default is None:
        default = []
    if raw is None or raw == '':
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


@jobs_bp.post('/<string:job_id>/apply')
@timing
def public_apply_to_job(job_id: str):
    """
    Public apply (no account): multipart form with profile fields + resume.
    Creates/updates passwordless candidates, saves profile, runs ATS, persists application.
    """
    try:
        is_multipart = request.content_type and 'multipart/form-data' in request.content_type
        if is_multipart:
            data = request.form.to_dict()
            data['education'] = _parse_json_field(data.get('education'), [])
            data['certifications'] = _parse_json_field(data.get('certifications'), [])
            data['experiences'] = _parse_json_field(data.get('experiences'), [])
        else:
            data = request.get_json(force=True) if request.is_json else {}

        resume_binary = None
        resume_filename = ''
        if is_multipart and request.files and 'resume' in request.files:
            resume_file = request.files['resume']
            if resume_file and resume_file.filename:
                resume_file.seek(0)
                resume_binary = resume_file.read()
                resume_filename = resume_file.filename
                if not isinstance(resume_binary, bytes):
                    resume_binary = bytes(resume_binary) if resume_binary else None

        has_resume = bool(resume_binary and len(resume_binary) > 0)
        err = validate_public_apply_payload(data, has_resume)
        if err:
            return jsonify({'error': err}), 400

        job = db_get(
            'SELECT * FROM jobs WHERE jdid = ? AND (enabled = ' + TRUE_SQL + ' OR enabled IS NULL)',
            (job_id,),
        )
        if not job:
            return jsonify({'error': 'Job not found or not available for applications'}), 404

        org = _public_org_from_request()
        if not org or not _job_matches_public_org(job, org):
            return jsonify({'error': 'Job not found or not available for applications'}), 404

        email = normalize_email(data.get('email'))
        full_name = (data.get('fullName') or '').strip()
        candidate_id = upsert_passwordless_candidate(full_name, email)

        existing = db_get(
            'SELECT id FROM applications WHERE candidate_id = ? AND job_id = ?',
            (candidate_id, job_id),
        )
        if existing:
            return jsonify({'error': 'Applicant already applied'}), 400

        data = {**data, 'email': email, 'fullName': full_name, 'completed': True}
        save_candidate_profile(candidate_id, data, resume_binary, completed=True)

        parsed_id = (data.get('parsedId') or data.get('parsed_id') or '').strip() or None
        public_uploader_id = (data.get('publicUploaderId') or data.get('public_uploader_id') or '').strip() or None
        parsed_resume_record = link_parsed_resume(parsed_id, candidate_id, public_uploader_id)
        if not parsed_resume_record:
            return jsonify({
                'error': 'No parsed resume found. Please upload your resume and wait for AI parsing to finish.'
            }), 400

        parsed_jd_record = db_get(
            """
            SELECT toon, confidence, id
            FROM parsed_jds
            WHERE job_id = ?
            ORDER BY created_at DESC
            """,
            (job_id,),
        )
        parsed_jd_id = (parsed_jd_record or {}).get('id')
        if parsed_jd_record:
            parsed_jd = toon_loads_flex(parsed_jd_record['toon'])
            if not parsed_jd:
                return jsonify({'error': 'Invalid stored job description parsing data'}), 400
        else:
            parsed_jd = _jd_toon_from_job_row(job)

        parsed_resume = toon_loads_flex(parsed_resume_record['toon'])
        if not parsed_resume or not isinstance(parsed_resume, dict) or not isinstance(parsed_jd, dict):
            return jsonify({'error': 'Resume or job description data is not in a valid format'}), 400

        ats_success, ats_result = match_candidate_to_job(
            candidate_id, job_id, parsed_resume, parsed_jd
        )
        if not ats_success or not ats_result:
            err_msg = (
                ats_result.get('error', 'Unknown ATS error')
                if isinstance(ats_result, dict)
                else str(ats_result)
            )
            return jsonify({'error': f'ATS matching failed: {err_msg}'}), 502

        final_score, shortlisted, rationale, ats_analysis_toon, status = _extract_ats_result(
            ats_result
        )
        app_id, match_id = _persist_application_atomic(
            candidate_id=candidate_id,
            job_id=job_id,
            parsed_resume_id=parsed_resume_record.get('id'),
            parsed_jd_id=parsed_jd_id,
            status=status,
            match_score=final_score,
            shortlisted=shortlisted,
            ats_reasoning=rationale,
            ats_analysis_toon=ats_analysis_toon,
        )

        if shortlisted and app_id:
            from app.domains.recruitment.services.interview_trigger import trigger_interview_scheduling
            from app.domains.recruitment.services.notifications import send_and_get_output
            profile = db_get('SELECT full_name, email FROM candidate_profiles WHERE candidate_id = ?', (candidate_id,))
            signup = db_get('SELECT email FROM candidates WHERE cid = ?', (candidate_id,))
            candidate_email = (profile or {}).get('email') or (signup or {}).get('email') or email or ''
            if candidate_email:
                try:
                    send_and_get_output(
                        hr_action='SHORTLISTED',
                        candidate_name=(profile or {}).get('full_name') or full_name or '',
                        candidate_email=candidate_email,
                        job_title=job.get('title') or '',
                        company_name=job.get('company') or '',
                        application_id=app_id,
                        timestamp=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                    )
                except Exception as notify_err:
                    print(f"[PUBLIC_APPLY] SHORTLISTED notification failed: {notify_err}")
            trigger_interview_scheduling(app_id, recruiter_hrid=job.get('posted_by'))

        return jsonify({
            'message': 'Application submitted successfully',
            'status': status.lower() if isinstance(status, str) else status,
            'matchScore': final_score,
            'shortlisted': shortlisted,
            'applicationId': app_id,
            'candidateId': candidate_id,
            'resumeFileName': resume_filename or None,
            'matchId': match_id,
        }), 200
    except Exception as e:
        print(f"[PUBLIC_APPLY] ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error'}), 500
