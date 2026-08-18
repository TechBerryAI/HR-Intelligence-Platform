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

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

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
