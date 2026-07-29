"""Authentication and authorization decorators for Flask routes."""
from functools import wraps

import jwt
from flask import jsonify, request

from app.core.auth import JWT_SECRET, auth_log
from app.domains.identity.authorization.rbac import (
    ROLE_CANDIDATE,
    get_role,
    is_head_hr,
    is_staff_recruiter,
)


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
            request.user = user
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Invalid or expired token"}), 403
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 403
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


def require_candidate(f):
    @wraps(f)
    @authenticate_token
    def wrapper(*args, **kwargs):
        user = getattr(request, 'user', None)
        if not user or get_role(user) != ROLE_CANDIDATE:
            return jsonify({"error": "Candidate access required"}), 403
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
                    return jsonify({"error": "Invalid or expired token"}), 401
                request.user = user
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Invalid or expired token"}), 401
            except Exception:
                return jsonify({"error": "Invalid or expired token"}), 401
        return f(*args, **kwargs)
    return wrapper
