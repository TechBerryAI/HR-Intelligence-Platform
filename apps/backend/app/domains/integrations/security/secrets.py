"""Encrypt / decrypt integration credentials at rest (Fernet)."""
from __future__ import annotations

import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

_PREFIX = 'enc:v1:'


class IntegrationSecretsError(RuntimeError):
    """Raised when encryption is required but unavailable."""


try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore


def _insecure_secrets_allowed() -> bool:
    flask_debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    allow_insecure = os.getenv('ALLOW_INSECURE_INTEGRATION_SECRETS', 'false').lower() in (
        '1', 'true', 'yes', 'on',
    )
    return flask_debug or allow_insecure


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


def _get_fernet(*, require: bool = False):
    if Fernet is None:
        if require and not _insecure_secrets_allowed():
            raise IntegrationSecretsError(
                'cryptography.Fernet is unavailable; cannot store integration secrets'
            )
        return None
    from app.domains.integrations.config import get_secrets_key

    key = get_secrets_key()
    if not key:
        if _insecure_secrets_allowed():
            key = (os.getenv('JWT_SECRET') or 'dev-integration-secrets').strip()
            logger.warning('[integrations] Using fallback integration secrets key (dev only)')
        else:
            logger.error('[integrations] INTEGRATION_SECRETS_KEY is required in production')
            if require:
                raise IntegrationSecretsError(
                    'INTEGRATION_SECRETS_KEY is required to store integration secrets'
                )
            return None
    try:
        return Fernet(_derive_fernet_key(key))
    except Exception as exc:
        logger.warning('[integrations] Fernet init failed: %s', exc)
        if require and not _insecure_secrets_allowed():
            raise IntegrationSecretsError(f'Fernet init failed: {exc}') from exc
        return None


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == '':
        return value
    if value.startswith(_PREFIX):
        return value
    f = _get_fernet(require=True)
    if f is None:
        # Explicit insecure/dev mode only — never silently persist plaintext in production.
        if not _insecure_secrets_allowed():
            raise IntegrationSecretsError(
                'Cannot encrypt integration secret: encryption unavailable'
            )
        logger.warning('[integrations] Storing integration secret without encryption (dev only)')
        return value
    token = f.encrypt(value.encode('utf-8')).decode('utf-8')
    return f'{_PREFIX}{token}'


def decrypt_secret(value: str | None) -> str | None:
    if value is None or value == '':
        return value
    if not value.startswith(_PREFIX):
        return value
    f = _get_fernet(require=False)
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
