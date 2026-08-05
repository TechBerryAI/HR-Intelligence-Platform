"""Integration framework configuration (env-driven)."""
from __future__ import annotations

import os


def get_secrets_key() -> str | None:
    """Fernet key for encrypting provider credentials. Optional in local mock mode."""
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


PROVIDER_CATALOG = (
    {'id': 'linkedin', 'name': 'LinkedIn', 'id_prefix': 'LI'},
    {'id': 'naukri', 'name': 'Naukri', 'id_prefix': 'NK'},
    {'id': 'indeed', 'name': 'Indeed', 'id_prefix': 'ID'},
)

VALID_PROVIDERS = {p['id'] for p in PROVIDER_CATALOG}
