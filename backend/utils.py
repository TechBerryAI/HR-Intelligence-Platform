import os
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
import jwt

JWT_SECRET = os.getenv('JWT_SECRET', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE')
# Access token lifetime; default 1 hour. Refresh replaces it automatically so user stays logged in.
JWT_ACCESS_EXPIRY_SECONDS = int(os.getenv('JWT_ACCESS_EXPIRY_SECONDS', 3600))
# Refresh token lifetime; default 30 days. Used to get new access token without re-login.
JWT_REFRESH_EXPIRY_SECONDS = int(os.getenv('JWT_REFRESH_EXPIRY_SECONDS', 30 * 24 * 3600))


def build_jwt_payload(identity_dict, refresh=False):
    """Return a copy of identity_dict with type, iat, exp. refresh=False -> access token, refresh=True -> refresh token."""
    payload = dict(identity_dict)
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
        print(f"[AUTH] Authenticating request to {request.method} {request.path}")
        auth_header = request.headers.get('Authorization', '')
        print(f"[AUTH] Authorization header: {auth_header[:20]}..." if auth_header else "[AUTH] No Authorization header")
        token = auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else None
        if not token:
            print("[AUTH] No token found - returning 401")
            return jsonify({"error": "Access token required"}), 401
        try:
            user = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if user.get('type') == 'refresh':
                print("[AUTH] Refresh token used as access token - returning 403")
                return jsonify({"error": "Invalid or expired token"}), 403
            print(f"[AUTH] Token decoded successfully. User: {user}")
            request.user = user
        except jwt.ExpiredSignatureError:
            print("[AUTH] Token expired - returning 403")
            return jsonify({"error": "Invalid or expired token"}), 403
        except Exception as e:
            print(f"[AUTH] Token decode failed: {e} - returning 403")
            return jsonify({"error": "Invalid or expired token"}), 403
        print("[AUTH] Authentication successful")
        return f(*args, **kwargs)
    return wrapper


def require_hr(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        print(f"[HR CHECK] Checking HR access for {request.method} {request.path}")
        user = getattr(request, 'user', None)
        print(f"[HR CHECK] User: {user}")
        if not user or user.get('role') != 'HR':
            print(f"[HR CHECK] Access denied - role: {user.get('role') if user else 'none'}")
            return jsonify({"error": "HR access required"}), 403
        print("[HR CHECK] HR access granted")
        return f(*args, **kwargs)
    return wrapper


def require_candidate(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not getattr(request, 'user', None) or request.user.get('role') != 'candidate':
            return jsonify({"error": "Candidate access required"}), 403
        return f(*args, **kwargs)
    return wrapper


def optional_authenticate_token(f):
    """If Authorization Bearer is present, require valid JWT (401 on invalid/expired). If no header, set request.user = None."""
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
