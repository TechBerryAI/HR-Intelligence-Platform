"""Integration-level bulk lease crash recovery against live Postgres."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.domains.administration.repositories import bulk_session_db as bdb


def _db_available() -> bool:
    try:
        from app.database.connection.db import db_get

        db_get('SELECT 1 AS ok')
        return True
    except Exception:
        return False


@pytest.mark.integration
def test_bulk_crash_recovery_lease_expires_then_other_worker_claims():
    """
    worker A claims session + file
    → A dies (lease expires)
    → reclaim
    → worker B claims
    → B can complete file status
    """
    if not _db_available():
        pytest.skip('Postgres unavailable for bulk crash recovery test')

    # Need a real hr_signup for FK on bulk_parse_sessions.created_by
    from app.database.connection.db import db_get, db_run

    owner = db_get('SELECT hrid FROM hr_signup LIMIT 1')
    if not owner:
        pytest.skip('No hr_signup row available for bulk session FK')

    hrid = owner['hrid']
    session_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    filename = f'recovery_{uuid.uuid4().hex[:8]}.pdf'

    try:
        db_run(
            """
            INSERT INTO bulk_parse_sessions (
                id, created_by, status, progress, total_files, started_at
            ) VALUES (?, ?, 'Queued', 0, 1, NOW())
            """,
            (session_id, hrid),
        )
        db_run(
            """
            INSERT INTO bulk_parse_files (
                id, session_id, original_filename, file_hash, status
            ) VALUES (?, ?, ?, ?, 'Queued')
            """,
            (file_id, session_id, filename, 'abc'),
        )

        # Worker A claims session + file
        assert bdb.claim_session_lease(session_id, 'worker-A', total_files=1) is True
        assert bdb.claim_file_for_processing(file_id, 'worker-A') is True

        # Second worker cannot claim while lease is fresh
        assert bdb.claim_session_lease(session_id, 'worker-B') is False
        assert bdb.claim_file_for_processing(file_id, 'worker-B') is False

        # Simulate worker A death: expire leases
        past = datetime.now(timezone.utc) - timedelta(seconds=30)
        db_run(
            """
            UPDATE bulk_parse_sessions
            SET leased_until = ?, updated_at = NOW()
            WHERE id = ?
            """,
            (past, session_id),
        )
        db_run(
            """
            UPDATE bulk_parse_files
            SET leased_until = ?, updated_at = NOW()
            WHERE id = ?
            """,
            (past, file_id),
        )

        reclaimed = bdb.reclaim_stale_file_leases()
        assert reclaimed >= 1

        file_row = db_get('SELECT status, leased_by FROM bulk_parse_files WHERE id = ?', (file_id,))
        assert file_row['status'] == 'Queued'
        assert file_row.get('leased_by') is None

        # Worker B recovers
        assert bdb.claim_session_lease(session_id, 'worker-B', total_files=1) is True
        assert bdb.claim_file_for_processing(file_id, 'worker-B') is True

        bdb.update_file_status(session_id, filename, 'Completed')
        bdb.finalize_session(session_id, started_at=__import__('time').time() - 1, successful=1, failed=0)

        done = db_get(
            'SELECT status, successful_files FROM bulk_parse_sessions WHERE id = ?',
            (session_id,),
        )
        assert done['status'] == 'Completed'
        file_done = db_get('SELECT status FROM bulk_parse_files WHERE id = ?', (file_id,))
        assert file_done['status'] == 'Completed'
    finally:
        db_run('DELETE FROM bulk_parse_files WHERE session_id = ?', (session_id,))
        db_run('DELETE FROM bulk_parse_sessions WHERE id = ?', (session_id,))
