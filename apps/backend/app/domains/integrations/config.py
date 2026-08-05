"""Integration framework configuration (env-driven)."""
from __future__ import annotations

import os
import re


def get_secrets_key() -> str | None:
    """Fernet key for encrypting provider credentials."""
    key = (os.getenv('INTEGRATION_SECRETS_KEY') or '').strip()
    return key or None


def get_max_retries() -> int:
    try:
        return max(0, int(os.getenv('INTEGRATION_MAX_RETRIES', '3')))
    except ValueError:
        return 3


def get_retry_base_seconds() -> float:
    try:
        return max(0.1, float(os.getenv('INTEGRATION_RETRY_BASE_SECONDS', '1.0')))
    except ValueError:
        return 1.0


def get_worker_max_workers() -> int:
    try:
        return max(1, int(os.getenv('INTEGRATION_WORKER_MAX_WORKERS', '4')))
    except ValueError:
        return 4


def get_auto_sync_interval_seconds() -> int:
    try:
        return max(60, int(os.getenv('INTEGRATION_AUTO_SYNC_INTERVAL_SECONDS', '900')))
    except ValueError:
        return 900


# Fixed built-in adapters only. Everything else is a custom HTTP platform.
PROVIDER_CATALOG = (
    {'id': 'linkedin', 'name': 'LinkedIn', 'id_prefix': 'LI', 'adapter': 'linkedin'},
    {'id': 'naukri', 'name': 'Naukri', 'id_prefix': 'NK', 'adapter': 'naukri'},
)

BUILTIN_PROVIDERS = {p['id'] for p in PROVIDER_CATALOG}
# Back-compat alias
VALID_PROVIDERS = BUILTIN_PROVIDERS

_SLUG_RE = re.compile(r'^[a-z][a-z0-9_]{1,62}$')


def slugify_provider(name: str | None) -> str:
    raw = (name or '').strip().lower()
    raw = re.sub(r'[^a-z0-9]+', '_', raw)
    raw = re.sub(r'_+', '_', raw).strip('_')
    if not raw:
        return ''
    if raw[0].isdigit():
        raw = f'p_{raw}'
    return raw[:63]


def is_valid_provider_slug(provider: str | None) -> bool:
    return bool(provider and _SLUG_RE.match(provider))


def is_builtin(provider: str | None) -> bool:
    return (provider or '').strip().lower() in BUILTIN_PROVIDERS
