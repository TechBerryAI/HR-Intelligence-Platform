import os
import re
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import jwt

from rbac import ROLE_CANDIDATE, ROLE_RECRUITER, ROLE_HEAD_HR, get_role, is_staff_recruiter, is_head_hr

PASSWORD_MIN_LENGTH = 8


def validate_password_strength(password):
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        return False, f'Password must be at least {PASSWORD_MIN_LENGTH} characters.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter.'
    if not re.search(r'\d', password):
        return False, 'Password must contain at least one number.'
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?`~]', password):
        return False, 'Password must contain at least one special character (e.g. !@#$%^&*).'
    return True, None


JWT_SECRET = os.getenv('JWT_SECRET', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE')
JWT_ACCESS_EXPIRY_SECONDS = int(os.getenv('JWT_ACCESS_EXPIRY_SECONDS', 3600))
JWT_REFRESH_EXPIRY_SECONDS = int(os.getenv('JWT_REFRESH_EXPIRY_SECONDS', 30 * 24 * 3600))

_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'


def _auth_log(message):
    if _DEBUG:
        print(message)


def build_jwt_payload(identity_dict, refresh=False):
    """JWT claims: user_id, role, email, type, iat, exp."""
    payload = {
        'user_id': identity_dict['user_id'],
        'role': identity_dict['role'],
        'email': identity_dict['email'],
    }
    now = datetime.utcnow()
    payload['iat'] = now
    payload['type'] = 'refresh' if refresh else 'access'
    payload['exp'] = now + timedelta(
        seconds=JWT_REFRESH_EXPIRY_SECONDS if refresh else JWT_ACCESS_EXPIRY_SECONDS
    )
    return payload


def authenticate_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        _auth_log(f"[AUTH] Authenticating request to {request.method} {request.path}")
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
