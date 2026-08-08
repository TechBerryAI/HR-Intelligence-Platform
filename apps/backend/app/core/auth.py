"""JWT helpers and password validation."""
import os
import re
from datetime import datetime, timedelta

PASSWORD_MIN_LENGTH = 8

JWT_SECRET = os.getenv('JWT_SECRET', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZXhhbXBsZSJ9.lGrIa8yMwsB_ZSrgoniyr5FF34e9tE7TJboLqTfvifE')
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
    """JWT claims: user_id, role, email, organization_id (optional), type, iat, exp."""
    payload = {
        'user_id': identity_dict['user_id'],
        'role': identity_dict['role'],
        'email': identity_dict['email'],
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
