"""Encrypt / decrypt integration credentials at rest (Fernet)."""
from __future__ import annotations

import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

_PREFIX = 'enc:v1:'

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore


def _derive_fernet_key(raw: str) -> bytes:
    """Accept a Fernet key or any secret string (derive 32-byte urlsafe key)."""
    raw = (raw or '').strip()
    if not raw:
        raise ValueError('empty secrets key')
    try:
        encoded = raw.encode('utf-8') if isinstance(raw, str) else raw
        if Fernet is not None:
            Fernet(encoded)
            return encoded
    except Exception:
        pass
    digest = hashlib.sha256(raw.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(digest)


def _get_fernet():
    if Fernet is None:
        return None
    from app.domains.integrations.config import get_secrets_key

    key = get_secrets_key()
    if not key:
        key = (os.getenv('JWT_SECRET') or 'dev-integration-secrets').strip()
    try:
        return Fernet(_derive_fernet_key(key))
    except Exception as exc:
        logger.warning('[integrations] Fernet init failed: %s', exc)
        return None


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == '':
        return value
    if value.startswith(_PREFIX):
        return value
    f = _get_fernet()
    if f is None:
        return value
    token = f.encrypt(value.encode('utf-8')).decode('utf-8')
    return f'{_PREFIX}{token}'


def decrypt_secret(value: str | None) -> str | None:
    if value is None or value == '':
        return value
    if not value.startswith(_PREFIX):
        return value
    f = _get_fernet()
    if f is None:
        return value
    token = value[len(_PREFIX) :]
    try:
        return f.decrypt(token.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        logger.warning('[integrations] Failed to decrypt secret (invalid token)')
        return None
    except Exception as exc:
        logger.warning('[integrations] Decrypt error: %s', exc)
        return None


def mask_secret(value: str | None) -> str | None:
    if value is None or value == '':
        return None
    return '••••••••'


def is_secret_configured(value: str | None) -> bool:
    return bool(value)
