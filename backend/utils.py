import os
from functools import wraps
from flask import request, jsonify
import jwt

JWT_SECRET = os.getenv('JWT_SECRET', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE')


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
