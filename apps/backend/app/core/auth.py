"""JWT helpers and password validation."""
import os
import re
import uuid
from datetime import datetime, timedelta

PASSWORD_MIN_LENGTH = 8

_PLACEHOLDER_JWT_SECRETS = {
    '',
    'your-jwt-secret-change-in-production',
    'changeme',
    'secret',
    'replace-with-a-unique-secret-at-least-32-chars',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE',
}


def _resolve_jwt_secret() -> str:
    secret = (os.getenv('JWT_SECRET') or '').strip()
    flask_debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    allow_dev = os.getenv('ALLOW_INSECURE_JWT', 'false').lower() in ('1', 'true', 'yes', 'on')
    if secret and secret not in _PLACEHOLDER_JWT_SECRETS and len(secret) >= 32:
        return secret
    if flask_debug or allow_dev:
        # Deterministic local-only fallback so restarts don't invalidate tokens mid-dev.
        return secret if secret and secret not in _PLACEHOLDER_JWT_SECRETS else (
            'dev-only-insecure-jwt-secret-do-not-use-in-prod'
        )
    raise RuntimeError(
        'JWT_SECRET must be set to a unique value of at least 32 characters. '
        'Remove placeholder values before starting in production.'
    )


JWT_SECRET = _resolve_jwt_secret()
JWT_ACCESS_EXPIRY_SECONDS = int(os.getenv('JWT_ACCESS_EXPIRY_SECONDS', 3600))
JWT_REFRESH_EXPIRY_SECONDS = int(os.getenv('JWT_REFRESH_EXPIRY_SECONDS', 30 * 24 * 3600))

_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'


def auth_log(message):
    if _DEBUG:
        print(message)


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


def build_jwt_payload(identity_dict, refresh=False):
    """JWT claims: user_id, role, email, organization_id (optional), type, iat, exp, jti."""
    payload = {
        'user_id': identity_dict['user_id'],
        'role': identity_dict['role'],
        'email': identity_dict['email'],
        'jti': str(uuid.uuid4()),
    }
    if identity_dict.get('organization_id'):
        payload['organization_id'] = str(identity_dict['organization_id'])
    if identity_dict.get('company'):
        payload['company'] = identity_dict['company']
    if identity_dict.get('org_slug'):
        payload['org_slug'] = identity_dict['org_slug']
    if identity_dict.get('org_name'):
        payload['org_name'] = identity_dict['org_name']
    now = datetime.utcnow()
    payload['iat'] = now
    payload['type'] = 'refresh' if refresh else 'access'
    payload['exp'] = now + timedelta(
        seconds=JWT_REFRESH_EXPIRY_SECONDS if refresh else JWT_ACCESS_EXPIRY_SECONDS
    )
    return payload
