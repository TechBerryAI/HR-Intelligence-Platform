"""Concurrent HRID allocation must not collide."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from live_db_helpers import _require_database


def test_next_hrid_concurrency():
    _require_database()
    import os
    import sys
    from pathlib import Path

    BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    os.environ.setdefault('FLASK_DEBUG', 'true')
    os.environ.setdefault('ALLOW_INSECURE_JWT', 'true')
    os.environ.setdefault('JWT_SECRET', 'ci-test-jwt-secret-at-least-32-characters-long')

    from app.domains.identity.services.hrid import next_hrid
    from app.database.connection.db import db_run, db_get
    import uuid
    import bcrypt

    # Ensure at least one row exists so MAX works
    from app.domains.identity.services.organizations import ensure_organization

    org_id = ensure_organization(f'HridRace {uuid.uuid4().hex[:8]}', create_only=True)
    pw = bcrypt.hashpw(b'Str0ng!Pass9', bcrypt.gensalt()).decode()

    def allocate_and_insert(_i: int) -> str:
        hrid = next_hrid()
        db_run(
            """
            INSERT INTO hr_signup (
                hrid, full_name, email, company, password, role,
                account_status, organization_id
            ) VALUES (?, ?, ?, 'Race Co', ?, 'RECRUITER', 'active', ?)
            """,
            (hrid, f'Race {_i}', f'race-{uuid.uuid4().hex}@example.com', pw, org_id),
        )
        return hrid

    n = 12
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [pool.submit(allocate_and_insert, i) for i in range(n)]
        ids = [f.result() for f in as_completed(futs)]

    assert len(ids) == n
    assert len(set(ids)) == n
