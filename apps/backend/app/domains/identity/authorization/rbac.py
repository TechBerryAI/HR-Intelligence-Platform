"""
Centralized RBAC — CEO, HEAD_HR, RECRUITER.
Future modules add permissions here only.
"""
from functools import wraps
from flask import request, jsonify

ROLE_CEO = 'CEO'
ROLE_HEAD_HR = 'HEAD_HR'
ROLE_RECRUITER = 'RECRUITER'

ALL_ROLES = {ROLE_CEO, ROLE_HEAD_HR, ROLE_RECRUITER}
STAFF_ROLES = {ROLE_CEO, ROLE_HEAD_HR, ROLE_RECRUITER}

PERMISSIONS = {
    'analytics:read': {ROLE_CEO, ROLE_HEAD_HR},
    'jobs:read_all': {ROLE_CEO, ROLE_HEAD_HR},
    'jobs:read_own': {ROLE_RECRUITER, ROLE_HEAD_HR, ROLE_CEO},
    'jobs:write_own': {ROLE_RECRUITER, ROLE_HEAD_HR},
    'jobs:write_any': {ROLE_HEAD_HR},
    'candidates:read_all': {ROLE_CEO, ROLE_HEAD_HR},
    'candidates:read_own': {ROLE_RECRUITER, ROLE_HEAD_HR, ROLE_CEO},
    'candidates:act_own': {ROLE_RECRUITER, ROLE_HEAD_HR},
    'candidates:act_any': {ROLE_HEAD_HR},
    'hr_users:manage': {ROLE_HEAD_HR},
    'bulk_parse:run': {ROLE_RECRUITER, ROLE_HEAD_HR},
    'bulk_parse:read_all': {ROLE_CEO, ROLE_HEAD_HR},
    'bulk_parse:read_own': {ROLE_RECRUITER, ROLE_HEAD_HR, ROLE_CEO},
    'settings:configure': {ROLE_HEAD_HR},
}


def get_user_id(user):
    if not user:
        return None
    return user.get('user_id')


def get_role(user):
    if not user:
        return None
    role = user.get('role')
    return role if role in ALL_ROLES else None


def has_permission(user, permission):
    role = get_role(user)
    if not role:
        return False
    return role in PERMISSIONS.get(permission, set())


def is_read_only(user):
    return get_role(user) == ROLE_CEO


def is_head_hr(user):
    return get_role(user) == ROLE_HEAD_HR


def is_recruiter(user):
    return get_role(user) == ROLE_RECRUITER


def is_staff_recruiter(user):
    """RECRUITER or HEAD_HR — operational recruitment workflows (not CEO read-only)."""
    return get_role(user) in (ROLE_RECRUITER, ROLE_HEAD_HR)


def can_access_job(user, posted_by):
    role = get_role(user)
    if role in (ROLE_CEO, ROLE_HEAD_HR):
        return True
    if role == ROLE_RECRUITER:
        return posted_by == get_user_id(user)
    return False


def can_modify_job(user, posted_by):
    if is_read_only(user):
        return False
    role = get_role(user)
    if role == ROLE_HEAD_HR:
        return True
    if role == ROLE_RECRUITER:
        return posted_by == get_user_id(user)
    return False


def can_access_application(user, job_posted_by):
    return can_access_job(user, job_posted_by)


def can_act_on_application(user, job_posted_by):
    if is_read_only(user):
        return False
    role = get_role(user)
    if role == ROLE_HEAD_HR:
        return True
    if role == ROLE_RECRUITER:
        return job_posted_by == get_user_id(user)
    return False


def can_access_bulk_session(user, started_by):
    role = get_role(user)
    if role in (ROLE_HEAD_HR, ROLE_CEO):
        return True
    if role == ROLE_RECRUITER:
        return started_by == get_user_id(user)
    return False


def job_list_scope(user):
    role = get_role(user)
    if role in (ROLE_CEO, ROLE_HEAD_HR):
        return '', ()
    uid = get_user_id(user)
    if role == ROLE_RECRUITER and uid:
        return 'j.posted_by = ?', (uid,)
    return '1 = 0', ()


def resolve_hr_role(signup_data):
    """DB role column -> JWT/API role."""
    db_role = (signup_data.get('role') or ROLE_RECRUITER).upper()
    if db_role not in (ROLE_CEO, ROLE_HEAD_HR, ROLE_RECRUITER):
        return ROLE_RECRUITER
    return db_role


def build_hr_identity(signup_data):
    return {
        'user_id': signup_data['hrid'],
        'email': signup_data['email'],
        'role': resolve_hr_role(signup_data),
    }


def build_jwt_identity(user_id, email, role):
    return {'user_id': user_id, 'email': email, 'role': role}


def require_analytics_read(f):
    from app.api.middleware.auth import authenticate_token

    @wraps(f)
    @authenticate_token
    def wrapper(*args, **kwargs):
        user = getattr(request, 'user', None)
        if not has_permission(user, 'analytics:read'):
            return jsonify({'error': 'Access denied'}), 403
        return f(*args, **kwargs)
    return wrapper
