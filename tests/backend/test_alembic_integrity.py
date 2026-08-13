"""Alembic orphan-stamp and head-integrity guards."""
from __future__ import annotations

import pytest

from app.database.alembic_runner import (
    AlembicOrphanStampError,
    orphan_stamp_action,
)


KNOWN = {
    '20260810_s001',
    '008763c9ff0f',
    '20260811_email',
    '20260812_candidates_org',
    '20260812_oauth_scrub',
    '20260812_bulk_leases',
    '20260812_ext_outbox',
}


def test_known_revision_is_ok(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    assert orphan_stamp_action('20260812_ext_outbox', KNOWN) == 'ok'
    assert orphan_stamp_action('20260811_email', KNOWN) == 'ok'
    assert orphan_stamp_action(None, KNOWN) == 'ok'
    assert orphan_stamp_action('', KNOWN) == 'ok'


def test_production_refuses_unknown_future_revision(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    with pytest.raises(AlembicOrphanStampError) as exc:
        orphan_stamp_action('20260899_future_head', KNOWN)
    assert '20260899_future_head' in str(exc.value)
    assert 'Refusing to rewrite' in str(exc.value)


def test_production_refuses_deleted_pre_squash_stamp(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    with pytest.raises(AlembicOrphanStampError):
        orphan_stamp_action('20260810_0014', KNOWN)


def test_debug_repairs_allowlisted_deleted_revision(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    assert orphan_stamp_action('20260810_0014', KNOWN) == 'repair'
    assert orphan_stamp_action('20260811_s005', KNOWN) == 'repair'


def test_debug_refuses_unknown_non_allowlisted_revision(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    with pytest.raises(AlembicOrphanStampError):
        orphan_stamp_action('20260899_future_head', KNOWN)


def test_migration_lock_key_is_stable_and_distinct_from_autosync():
    from app.database.alembic_runner import MIGRATION_ADVISORY_LOCK_KEY
    from app.domains.integrations.scheduler import AUTO_SYNC_ADVISORY_LOCK_KEY

    assert MIGRATION_ADVISORY_LOCK_KEY == 872_014_002
    assert MIGRATION_ADVISORY_LOCK_KEY != AUTO_SYNC_ADVISORY_LOCK_KEY


def test_postgres_application_name_sanitizes_role(monkeypatch):
    from app.database.connection.db import postgres_application_name

    monkeypatch.setenv('HCIP_PROCESS_ROLE', 'Web Worker!')
    monkeypatch.setenv('HCIP_RELEASE_ID', '20260812_ext')
    name = postgres_application_name()
    assert name.startswith('hcip-')
    assert ' ' not in name
    assert len(name) <= 63
    assert 'web' in name
    assert '20260812_ext' in name


@pytest.mark.integration
def test_live_alembic_current_matches_head():
    """When Postgres is reachable, version table must equal the application head."""
    try:
        from app.database.connection.db import db_get
        row = db_get('SELECT 1 AS ok')
        if not row:
            pytest.skip('Postgres not reachable')
    except Exception as exc:
        pytest.skip(f'Postgres not reachable: {exc}')

    ver = db_get('SELECT version_num FROM alembic_version LIMIT 1')
    current = (ver or {}).get('version_num')
    assert current == '20260812_ext_outbox', (
        f'alembic_version={current!r}; expected 20260812_ext_outbox. '
        'Run: cd apps/backend && alembic upgrade head'
    )
    markers = db_get(
        """
        SELECT
          (SELECT 1 FROM information_schema.columns
             WHERE table_schema = current_schema()
               AND table_name = 'external_jobs'
               AND column_name = 'leased_until') AS ext_lease,
          (SELECT 1 FROM information_schema.columns
             WHERE table_schema = current_schema()
               AND table_name = 'bulk_parse_files'
               AND column_name = 'leased_until') AS bulk_lease,
          (SELECT 1 FROM pg_indexes
             WHERE indexname = 'ux_candidates_org_normalized_email') AS cand_ux,
          (SELECT 1 FROM pg_indexes
             WHERE indexname = 'ix_external_jobs_outbox_claim') AS outbox_ix
        """
    )
    assert markers and markers.get('ext_lease')
    assert markers.get('bulk_lease')
    assert markers.get('cand_ux')
    assert markers.get('outbox_ix')
