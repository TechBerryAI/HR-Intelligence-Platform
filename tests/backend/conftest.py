"""Shared pytest configuration for backend tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow importing app.core.auth without a production JWT in the unit-test process.
os.environ.setdefault('FLASK_DEBUG', 'true')
os.environ.setdefault('ALLOW_INSECURE_JWT', 'true')
os.environ.setdefault('JWT_SECRET', 'ci-test-jwt-secret-at-least-32-characters-long')

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
