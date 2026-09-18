"""Shared pytest configuration for backend tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Allow importing app.core.auth without a production JWT in the unit-test process.
os.environ.setdefault('FLASK_DEBUG', 'true')
os.environ.setdefault('ALLOW_INSECURE_JWT', 'true')
os.environ.setdefault('JWT_SECRET', 'ci-test-jwt-secret-at-least-32-characters-long')

# create_app load_dotenv does not override existing keys. Pin REDIS_URL so a
# developer .env cannot stall unit tests on a remote Redis ping (2s).
# Live Redis tests set TEST_REDIS_URL. Do not blank OLLAMA_MODEL here — smoke
# tests need the operator pin.
_test_redis = (os.environ.get('TEST_REDIS_URL') or '').strip()
os.environ['REDIS_URL'] = _test_redis

# Same reasoning, much higher stakes: create_app/db.py's own load_dotenv() calls
# only fill in *unset* keys, so a developer's real apps/backend/.env (which may
# point at a live/shared database, e.g. a team's LAN Postgres) would otherwise be
# picked up by any test that touches the DB — including tests with no explicit
# live-DB opt-in. This module runs before create_app/db.py ever calls
# load_dotenv(), so os.environ here reflects only what the invoking shell/CI
# actually exported (e.g. CI's `env:` block), never the local .env file yet.
# If nothing meaningful was explicitly exported, force a harmless local-only
# target so the worst case for a plain local `pytest` run is "connection
# refused to 127.0.0.1", never a write to someone else's real database. A
# developer who wants live-DB tests locally should `export DATABASE_URL=...`
# (or POSTGRES_USER/PASSWORD) before invoking pytest, exactly as CI does —
# that's detected here and left untouched.
_DB_ALREADY_CONFIGURED = bool((os.environ.get('DATABASE_URL') or '').strip()) or bool(
    os.environ.get('POSTGRES_USER') and os.environ.get('POSTGRES_PASSWORD')
)
if not _DB_ALREADY_CONFIGURED:
    os.environ['DATABASE_URL'] = ''
    os.environ['POSTGRES_HOST'] = '127.0.0.1'
    os.environ['POSTGRES_PORT'] = '5432'
    os.environ['POSTGRES_DB'] = 'nonexistent_test_db'
    # Left blank on purpose: live_db_helpers._require_database() skips whenever
    # both are falsy, which is the correct default for a plain unit-test run.
    os.environ['POSTGRES_USER'] = ''
    os.environ['POSTGRES_PASSWORD'] = ''

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Allow `from live_db_helpers import ...` in sibling test modules
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from app.core.log_redaction import install_log_redaction  # noqa: E402

install_log_redaction()


def _isolate_redis_url() -> None:
    """Undo runtime_adapter load_dotenv(override=True) leaking operator REDIS_URL."""
    if (os.environ.get('TEST_REDIS_URL') or '').strip():
        return
    os.environ['REDIS_URL'] = ''
    try:
        import app.core.shared_store as ss

        ss._REDIS_URL = ''
        ss._redis_client = None
        ss._redis_tried = False
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _isolate_redis_url_each_test():
    _isolate_redis_url()
    yield
    _isolate_redis_url()


def _isolate_database_url() -> None:
    """Undo runtime_adapter load_dotenv(override=True) leaking operator DB creds."""
    if _DB_ALREADY_CONFIGURED:
        return
    os.environ['DATABASE_URL'] = ''
    os.environ['POSTGRES_HOST'] = '127.0.0.1'
    os.environ['POSTGRES_PORT'] = '5432'
    os.environ['POSTGRES_DB'] = 'nonexistent_test_db'
    os.environ['POSTGRES_USER'] = ''
    os.environ['POSTGRES_PASSWORD'] = ''


@pytest.fixture(autouse=True)
def _isolate_database_url_each_test():
    _isolate_database_url()
    yield
    _isolate_database_url()
