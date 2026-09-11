"""Authentication and authorization decorators for Flask routes."""
from functools import wraps

import jwt
from flask import jsonify, request

from app.core.auth import JWT_SECRET, auth_log
from app.database.connection.db import db_get
from app.domains.identity.authorization.rbac import (
    is_head_hr,
    is_staff_recruiter,
    resolve_hr_role,
)
from app.domains.identity.sessions.service import user_has_active_refresh_session


def _load_active_hr_user(user_id: str) -> dict | None:
    if not user_id:
        return None
    row = db_get(
        """
        SELECT hrid, email, role, account_status, organization_id, company
        FROM hr_signup WHERE hrid = ?
        """,
        (user_id,),
    )
    if not row or (row.get('account_status') or 'active') != 'active':
        return None
    return row


def authenticate_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_log(f"[AUTH] Authenticating request to {request.method} {request.path}")
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else None
        if not token:
            return jsonify({"error": "Access token required"}), 401
        try:
            user = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if user.get('type') == 'refresh':
                return jsonify({"error": "Invalid or expired token"}), 403
            user_id = user.get('user_id')
            signup = _load_active_hr_user(user_id)
            if not signup:
                return jsonify({"error": "Invalid or expired token"}), 401
            if not user_has_active_refresh_session(user_id):
                return jsonify({"error": "Invalid or expired token"}), 401
            # Align role / org with DB (covers demotion without waiting for token expiry)
            user['role'] = resolve_hr_role(signup)
            if signup.get('organization_id'):
                user['organization_id'] = str(signup['organization_id'])
            if signup.get('email'):
                user['email'] = signup['email']
            request.user = user
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Invalid or expired token"}), 401
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401
        return f(*args, **kwargs)
    return wrapper


def require_recruiter(f):
    """RECRUITER or HEAD_HR — operational recruitment (not CEO read-only)."""
    @wraps(f)
    @authenticate_token
    def wrapper(*args, **kwargs):
        user = getattr(request, 'user', None)
        if not user or not is_staff_recruiter(user):
            return jsonify({"error": "Recruiter access required"}), 403
        return f(*args, **kwargs)
    return wrapper


def require_head_hr(f):
    @wraps(f)
    @authenticate_token
    def wrapper(*args, **kwargs):
        user = getattr(request, 'user', None)
        if not user or not is_head_hr(user):
            return jsonify({"error": "Head of HR access required"}), 403
        return f(*args, **kwargs)
    return wrapper


def optional_authenticate_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else None
        request.user = None
        if token:
            try:
                user = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
                if user.get('type') == 'refresh':
                    # Treat refresh tokens as unauthenticated for optional routes
                    request.user = None
                else:
                    user_id = user.get('user_id')
                    signup = _load_active_hr_user(user_id)
                    if not signup or not user_has_active_refresh_session(user_id):
                        request.user = None
                    else:
                        user['role'] = resolve_hr_role(signup)
                        if signup.get('organization_id'):
                            user['organization_id'] = str(signup['organization_id'])
                        if signup.get('email'):
                            user['email'] = signup['email']
                        request.user = user
            except jwt.ExpiredSignatureError:
                request.user = None
            except Exception:
                request.user = None
        return f(*args, **kwargs)
    return wrapper
