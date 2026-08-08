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
    'developer:performance': {ROLE_HEAD_HR},
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


def _resolve_job_organization_id(organization_id=None, posted_by=None) -> str | None:
    if organization_id:
        return str(organization_id)
    if not posted_by:
        return None
    try:
        from app.database.connection.db import db_get

        owner = db_get(
            'SELECT organization_id FROM hr_signup WHERE hrid = ?',
            (posted_by,),
        )
        if owner and owner.get('organization_id'):
            return str(owner['organization_id'])
        job = db_get(
            '''
            SELECT organization_id FROM jobs
            WHERE posted_by = ? AND organization_id IS NOT NULL
            ORDER BY posted_on DESC
            LIMIT 1
            ''',
            (posted_by,),
        )
        if job and job.get('organization_id'):
            return str(job['organization_id'])
    except Exception:
        return None
    return None


def same_organization(user, organization_id) -> bool:
    """True when user belongs to the given organization_id."""
    if not user or not organization_id:
        return False
    from app.domains.identity.services.organizations import get_organization_id_for_user

    user_org = get_organization_id_for_user(user)
    if not user_org:
        return False
    return str(user_org) == str(organization_id)


def can_access_job(user, posted_by=None, organization_id=None):
    """Staff may access jobs only within their organization."""
    role = get_role(user)
    if role not in STAFF_ROLES:
        return False
    job_org = _resolve_job_organization_id(organization_id=organization_id, posted_by=posted_by)
    return same_organization(user, job_org)


def can_modify_job(user, posted_by=None, organization_id=None):
    if is_read_only(user):
        return False
    role = get_role(user)
    if role not in (ROLE_HEAD_HR, ROLE_RECRUITER):
        return False
    return can_access_job(user, posted_by=posted_by, organization_id=organization_id)


def can_access_application(user, job_posted_by=None, organization_id=None):
    return can_access_job(user, posted_by=job_posted_by, organization_id=organization_id)


def can_act_on_application(user, job_posted_by=None, organization_id=None):
    if is_read_only(user):
        return False
    role = get_role(user)
    if role not in (ROLE_HEAD_HR, ROLE_RECRUITER):
        return False
    return can_access_job(user, posted_by=job_posted_by, organization_id=organization_id)


def can_access_bulk_session(user, started_by):
    """Org-scoped: Head HR/CEO see org sessions; recruiter sees own."""
    role = get_role(user)
    if role == ROLE_RECRUITER:
        return started_by == get_user_id(user)
    if role in (ROLE_HEAD_HR, ROLE_CEO):
        if started_by == get_user_id(user):
            return True
        try:
            from app.database.connection.db import db_get
            from app.domains.identity.services.organizations import get_organization_id_for_user

            user_org = get_organization_id_for_user(user)
            if not user_org or not started_by:
                return False
            owner = db_get(
                'SELECT organization_id FROM hr_signup WHERE hrid = ?',
                (started_by,),
            )
            return bool(owner and str(owner.get('organization_id') or '') == str(user_org))
        except Exception:
            return False
    return False


def job_list_scope(user):
    """SQL fragment filtering jobs to the caller's organization."""
    from app.domains.identity.services.organizations import get_organization_id_for_user

    org_id = get_organization_id_for_user(user)
    if org_id and get_role(user) in STAFF_ROLES:
        return 'j.organization_id = ?', (org_id,)
    return '1 = 0', ()


def resolve_hr_role(signup_data):
    """DB role column -> JWT/API role."""
    db_role = (signup_data.get('role') or ROLE_RECRUITER).upper()
    if db_role not in (ROLE_CEO, ROLE_HEAD_HR, ROLE_RECRUITER):
        return ROLE_RECRUITER
    return db_role


def build_hr_identity(signup_data):
    from app.domains.identity.services.organizations import enrich_signup_with_org

    data = enrich_signup_with_org(signup_data)
    identity = {
        'user_id': data['hrid'],
        'email': data['email'],
        'role': resolve_hr_role(data),
    }
    if data.get('organization_id'):
        identity['organization_id'] = str(data['organization_id'])
    if data.get('company'):
        identity['company'] = data['company']
    if data.get('org_slug'):
        identity['org_slug'] = data['org_slug']
    if data.get('org_name'):
        identity['org_name'] = data['org_name']
    return identity


def build_jwt_identity(user_id, email, role, organization_id=None, company=None, org_slug=None):
    identity = {'user_id': user_id, 'email': email, 'role': role}
    if organization_id:
        identity['organization_id'] = str(organization_id)
    if company:
        identity['company'] = company
    if org_slug:
        identity['org_slug'] = org_slug
    return identity


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
