"""Candidate profile routes for HR staff (no candidate self-service accounts)."""
from flask import Blueprint, jsonify, request

from app.api.middleware.auth import authenticate_token
from app.database.connection.db import db_all, db_get, BACKEND
from app.domains.identity.authorization.rbac import get_role, get_user_id, has_permission, ROLE_RECRUITER

candidate_bp = Blueprint('candidate', __name__)
CGPA_COL = '"cgpa/percentage"' if BACKEND == "postgresql" else "[cgpa/percentage]"


def parse_profile(profile: dict) -> dict:
    education_rows = db_all(
        'SELECT degree, institution, ' + CGPA_COL + ' as cgpa, start_date, end_date FROM candidate_education WHERE candidate_id = ? ORDER BY degree',
        (profile.get('candidate_id'),)
    ) if profile.get('candidate_id') else []
    formatted_education = [
        {
            'degree': row.get('degree') or '',
            'institution': row.get('institution') or '',
            'cgpa': row.get('cgpa') or '',
            'startMonth': row.get('start_date') or '',
            'endMonth': row.get('end_date') or '',
        }
        for row in (education_rows or [])
    ]
    certification_rows = db_all(
        '''
        SELECT certification, issuer, end_month
        FROM candidate_certifications
        WHERE candidate_id = ?
        ORDER BY certification
        ''',
        (profile.get('candidate_id'),)
    ) if profile.get('candidate_id') else []
    formatted_certifications = [
        {
            'certification': row.get('certification') or '',
            'issuer': row.get('issuer') or '',
            'endMonth': row.get('end_month') or '',
        }
        for row in (certification_rows or [])
    ]
    experience_rows = db_all(
        '''
        SELECT company, role, start_date, end_date, present
        FROM candidate_experiences
        WHERE candidate_id = ?
        ORDER BY company
        ''',
        (profile.get('candidate_id'),)
    ) if profile.get('candidate_id') else []
    formatted_experiences = [
        {
            'company': row.get('company') or '',
            'role': row.get('role') or '',
            'startMonth': row.get('start_date') or '',
            'endMonth': row.get('end_date') or '',
            'isCurrent': (row.get('present') or '').lower() == 'yes',
        }
        for row in (experience_rows or [])
    ]
    has_resume = profile.get('has_resume')
    resume_file_name = 'resume.pdf' if (has_resume not in (None, '', 0) or profile.get('resume') is not None) else ''
    return {
        'experienceLevel': profile.get('experience_level') or '',
        'servingNotice': profile.get('serving_notice') or '',
        'fullName': profile.get('full_name') or '',
        'email': profile.get('email') or '',
        'phone': profile.get('phone') or '',
        'noticePeriod': profile.get('notice_period') or '',
        'lastWorkingDay': profile.get('last_working_day') or '',
        'linkedinUrl': profile.get('linkedin_url') or '',
        'portfolioUrl': profile.get('portfolio_url') or '',
        'currentLocation': profile.get('current_location') or '',
        'preferredLocation': profile.get('preferred_location') or '',
        'resumeFileName': resume_file_name,
        'education': formatted_education,
        'certifications': formatted_certifications,
        'experiences': formatted_experiences,
        'completed': bool(profile.get('completed')),
    }


@candidate_bp.get('/profile/<string:candidate_id>')
@authenticate_token
def get_profile_admin(candidate_id: str):
    """HR/HEAD_HR/CEO view candidate profile scoped to caller's organization."""
    user = request.user
    if not has_permission(user, 'candidates:read_own'):
        return jsonify({'error': 'Access denied'}), 403
    from app.domains.identity.services.organizations import require_organization_id
    org_id, org_err = require_organization_id(user)
    if org_err:
        return org_err
    if get_role(user) == ROLE_RECRUITER:
        linked = db_get(
            '''
            SELECT 1 FROM applications a
            JOIN jobs j ON a.job_id = j.jdid
            WHERE a.candidate_id = ? AND j.posted_by = ? AND j.organization_id = ?
            LIMIT 1
            ''',
            (candidate_id, get_user_id(user), org_id),
        )
        if not linked:
            return jsonify({'error': 'Profile not found'}), 404
    else:
        linked = db_get(
            '''
            SELECT 1 FROM applications a
            JOIN jobs j ON a.job_id = j.jdid
            WHERE a.candidate_id = ? AND j.organization_id = ?
            LIMIT 1
            ''',
            (candidate_id, org_id),
        )
        if not linked:
            return jsonify({'error': 'Profile not found'}), 404
    try:
        profile = db_get(
            '''
            SELECT candidate_id, full_name, email, phone,
                   experience_level, serving_notice, notice_period, last_working_day,
                   linkedin_url, portfolio_url, current_location, preferred_location,
                   completed, updated_at,
                   CASE WHEN resume IS NOT NULL OR resume_raw_file_id IS NOT NULL THEN 1 ELSE 0 END as has_resume
            FROM candidate_profiles
            WHERE candidate_id = ?
            ''',
            (candidate_id,)
        )
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404

        return jsonify(parse_profile(profile))
    except Exception as e:
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
