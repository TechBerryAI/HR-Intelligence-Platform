"""
Super Admin blueprint — god-mode access for the system owner.
Credentials are stored in .env (SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD).
No public signup; this account is seeded by the system operator.
"""
import os
import secrets

import jwt
from flask import Blueprint, jsonify, request

from db import db_all, db_get, db_run
from utils import authenticate_token, build_jwt_payload, require_super_admin

super_admin_bp = Blueprint('super_admin', __name__)

JWT_SECRET = os.getenv(
    'JWT_SECRET',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE',
)
SUPER_ADMIN_EMAIL = (os.getenv('SUPER_ADMIN_EMAIL', 'superadmin@portal.com') or '').strip().lower()
SUPER_ADMIN_PASSWORD = (os.getenv('SUPER_ADMIN_PASSWORD', 'SuperAdmin@123!') or '').strip()
SUPER_ADMIN_NAME = (os.getenv('SUPER_ADMIN_NAME', 'Super Administrator') or '').strip()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@super_admin_bp.post('/login')
def super_admin_login():
    data = request.get_json(force=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    # Constant-time comparison to prevent timing attacks
    email_ok = secrets.compare_digest(email, SUPER_ADMIN_EMAIL)
    pass_ok = secrets.compare_digest(password, SUPER_ADMIN_PASSWORD)

    if not email_ok or not pass_ok:
        return jsonify({'error': 'Invalid credentials'}), 401

    identity = {'id': 'SUPER_ADMIN', 'email': SUPER_ADMIN_EMAIL, 'role': 'super_admin'}
    access_token = jwt.encode(build_jwt_payload(identity, refresh=False), JWT_SECRET, algorithm='HS256')
    refresh_token = jwt.encode(build_jwt_payload(identity, refresh=True), JWT_SECRET, algorithm='HS256')

    return jsonify({
        'token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': 'SUPER_ADMIN',
            'email': SUPER_ADMIN_EMAIL,
            'name': SUPER_ADMIN_NAME,
            'role': 'super_admin',
        },
    })


# ---------------------------------------------------------------------------
# Stats / Dashboard
# ---------------------------------------------------------------------------

@super_admin_bp.get('/stats')
@authenticate_token
@require_super_admin
def get_stats():
    total_admins = db_get('SELECT COUNT(*) AS cnt FROM hr_signup', ())
    total_candidates = db_get('SELECT COUNT(*) AS cnt FROM candidate_signup', ())
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
# Admins (HR users)
# ---------------------------------------------------------------------------

@super_admin_bp.get('/admins')
@authenticate_token
@require_super_admin
def list_admins():
    rows = db_all(
        'SELECT hrid, full_name, email, company, created_at FROM hr_signup ORDER BY created_at DESC',
        (),
    )
    return jsonify({'admins': rows})


@super_admin_bp.delete('/admins/<hrid>')
@authenticate_token
@require_super_admin
def delete_admin(hrid):
    existing = db_get('SELECT hrid FROM hr_signup WHERE hrid = ?', (hrid,))
    if not existing:
        return jsonify({'error': 'Admin not found'}), 404
    try:
        db_run('DELETE FROM hr_signup WHERE hrid = ?', (hrid,))
        return jsonify({'message': f'Admin {hrid} deleted successfully'})
    except Exception as e:
        print(f'[SUPER ADMIN] Error deleting admin {hrid}: {e}')
        return jsonify({'error': 'Failed to delete admin'}), 500


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

@super_admin_bp.get('/candidates')
@authenticate_token
@require_super_admin
def list_candidates():
    rows = db_all(
        '''SELECT cs.cid, cs.name, cs.email, cs.created_at,
                  cp.full_name, cp.phone, cp.experience_level,
                  cp.current_location, cp.completed
           FROM candidate_signup cs
           LEFT JOIN candidate_profiles cp ON cp.candidate_id = cs.cid
           ORDER BY cs.created_at DESC''',
        (),
    )
    return jsonify({'candidates': rows})


@super_admin_bp.delete('/candidates/<cid>')
@authenticate_token
@require_super_admin
def delete_candidate(cid):
    existing = db_get('SELECT cid FROM candidate_signup WHERE cid = ?', (cid,))
    if not existing:
        return jsonify({'error': 'Candidate not found'}), 404
    try:
        db_run('DELETE FROM candidate_signup WHERE cid = ?', (cid,))
        return jsonify({'message': f'Candidate {cid} deleted successfully'})
    except Exception as e:
        print(f'[SUPER ADMIN] Error deleting candidate {cid}: {e}')
        return jsonify({'error': 'Failed to delete candidate'}), 500


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@super_admin_bp.get('/jobs')
@authenticate_token
@require_super_admin
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


@super_admin_bp.delete('/jobs/<jdid>')
@authenticate_token
@require_super_admin
def delete_job(jdid):
    existing = db_get('SELECT jdid FROM jobs WHERE jdid = ?', (jdid,))
    if not existing:
        return jsonify({'error': 'Job not found'}), 404
    try:
        db_run('DELETE FROM jobs WHERE jdid = ?', (jdid,))
        return jsonify({'message': f'Job {jdid} deleted successfully'})
    except Exception as e:
        print(f'[SUPER ADMIN] Error deleting job {jdid}: {e}')
        return jsonify({'error': 'Failed to delete job'}), 500


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

@super_admin_bp.get('/applications')
@authenticate_token
@require_super_admin
def list_applications():
    rows = db_all(
        '''SELECT a.id, a.candidate_id, a.job_id, a.status,
                  a.applied_at, a.match_score, a.shortlisted,
                  cs.name AS candidate_name, cs.email AS candidate_email,
                  j.title AS job_title, j.company AS job_company,
                  h.full_name AS hr_name
           FROM applications a
           LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
           LEFT JOIN jobs j ON j.jdid = a.job_id
           LEFT JOIN hr_signup h ON h.hrid = j.posted_by
           ORDER BY a.applied_at DESC''',
        (),
    )
    return jsonify({'applications': rows})
