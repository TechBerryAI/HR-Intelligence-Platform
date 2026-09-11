"""Alembic orphan-stamp and head-integrity guards."""
from __future__ import annotations

import pytest

from app.database.alembic_runner import (
    AlembicOrphanStampError,
    SchemaMigrationPolicyError,
    SchemaNotAtHeadError,
    orphan_stamp_action,
    schema_at_head_status,
)


def _known_from_scripts() -> set[str]:
    """Live revision ids from this tree's Alembic scripts (not a hardcoded list)."""
    from app.database.alembic_runner import _known_revision_ids

    known = _known_revision_ids()
    assert known, 'Alembic script directory returned no revisions'
    return known


def _app_head() -> str:
    from app.database.alembic_runner import head_revision_ids

    heads = head_revision_ids()
    assert len(heads) == 1, heads
    return heads[0]


def test_known_revision_is_ok(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    known = _known_from_scripts()
    head = _app_head()
    assert head in known
    assert orphan_stamp_action(head, known) == 'ok'
    assert orphan_stamp_action('20260814_cid_pad3', known) == 'ok'
    assert orphan_stamp_action('20260812_ext_outbox', known) == 'ok'
    assert orphan_stamp_action('20260811_email', known) == 'ok'
    assert orphan_stamp_action('20260911_oauth_csrf', known) == 'ok'
    assert orphan_stamp_action('20260911_acct_deact', known) == 'ok'
    assert orphan_stamp_action(None, known) == 'ok'
    assert orphan_stamp_action('', known) == 'ok'


def test_production_refuses_unknown_future_revision(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    known = _known_from_scripts()
    with pytest.raises(AlembicOrphanStampError) as exc:
        orphan_stamp_action('20260899_future_head', known)
    assert '20260899_future_head' in str(exc.value)
    assert 'Refusing to rewrite' in str(exc.value)


def test_production_refuses_deleted_pre_squash_stamp(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    known = _known_from_scripts()
    with pytest.raises(AlembicOrphanStampError):
        orphan_stamp_action('20260810_0014', known)


def test_debug_repairs_allowlisted_deleted_revision(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    known = _known_from_scripts()
    assert orphan_stamp_action('20260810_0014', known) == 'repair'
    assert orphan_stamp_action('20260811_s005', known) == 'repair'


def test_debug_repairs_phantom_unmerged_stamp(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    known = _known_from_scripts()
    # No phantom repairs configured — unknown stamps still fail in debug.
    with pytest.raises(AlembicOrphanStampError):
        orphan_stamp_action('20260901_local_phantom', known)


def test_production_refuses_phantom_unmerged_stamp(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'false')
    known = _known_from_scripts()
    with pytest.raises(AlembicOrphanStampError):
        orphan_stamp_action('20260901_local_phantom', known)


def test_debug_refuses_unknown_non_allowlisted_revision(monkeypatch):
    monkeypatch.setenv('FLASK_DEBUG', 'true')
    known = _known_from_scripts()
    with pytest.raises(AlembicOrphanStampError):
        orphan_stamp_action('20260899_future_head', known)


def test_schema_at_head_status_ok():
    head = _app_head()
    assert schema_at_head_status(head, [head]) == head


def test_schema_at_head_status_rejects_mismatch():
    head = _app_head()
    with pytest.raises(SchemaNotAtHeadError) as exc:
        schema_at_head_status('20260810_s001', [head])
    assert '20260810_s001' in str(exc.value)
    assert head in str(exc.value)


def test_schema_at_head_status_rejects_empty_and_multiple_heads():
    head = _app_head()
    with pytest.raises(SchemaNotAtHeadError):
        schema_at_head_status(None, [head])
    with pytest.raises(SchemaNotAtHeadError):
        schema_at_head_status(head, ['a', 'b'])


def test_production_web_requires_migrations_already_applied(monkeypatch):
    from app.database.alembic_runner import prepare_schema_for_web_process

    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'false')
    monkeypatch.delenv('MIGRATIONS_ALREADY_APPLIED', raising=False)
    monkeypatch.delenv('HCIP_MIGRATIONS_DONE', raising=False)
    with pytest.raises(SchemaMigrationPolicyError) as exc:
        prepare_schema_for_web_process()
    assert 'MIGRATIONS_ALREADY_APPLIED' in str(exc.value)
    assert 'alembic upgrade head' in str(exc.value)


def test_production_web_verifies_and_does_not_upgrade(monkeypatch):
    from app.database import alembic_runner as runner

    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_INSECURE_JWT', 'false')
    monkeypatch.setenv('MIGRATIONS_ALREADY_APPLIED', 'true')

    def _fail_upgrade():
        raise AssertionError('upgrade_head must not run in production web')

    monkeypatch.setattr(runner, 'upgrade_head', _fail_upgrade)
    head = _app_head()
    monkeypatch.setattr(runner, 'verify_at_head', lambda: head)
    assert runner.prepare_schema_for_web_process() == head


def test_dev_web_upgrades_when_flag_unset(monkeypatch):
    from app.database import alembic_runner as runner

    monkeypatch.setenv('FLASK_DEBUG', 'true')
    monkeypatch.delenv('MIGRATIONS_ALREADY_APPLIED', raising=False)
    monkeypatch.delenv('HCIP_MIGRATIONS_DONE', raising=False)
    calls = {'upgrade': 0}

    def _upgrade():
        calls['upgrade'] += 1

    monkeypatch.setattr(runner, 'upgrade_head', _upgrade)
    head = _app_head()
    monkeypatch.setattr(runner, 'verify_at_head', lambda: head)
    runner.prepare_schema_for_web_process()
    assert calls['upgrade'] == 1


def test_hcip_migrations_done_is_alias_for_already_applied(monkeypatch):
    from app.database.alembic_runner import migrations_already_applied

    monkeypatch.delenv('MIGRATIONS_ALREADY_APPLIED', raising=False)
    monkeypatch.setenv('HCIP_MIGRATIONS_DONE', '1')
    assert migrations_already_applied() is True


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
    from app.database.alembic_runner import head_revision_ids

    try:
        from app.database.connection.db import db_get
        row = db_get('SELECT 1 AS ok')
        if not row:
            pytest.skip('Postgres not reachable')
    except Exception as exc:
        pytest.skip(f'Postgres not reachable: {exc}')

    heads = head_revision_ids()
    assert len(heads) == 1, heads
    ver = db_get('SELECT version_num FROM alembic_version LIMIT 1')
    current = (ver or {}).get('version_num')
    head = _app_head()
    assert current == head, (
        f'alembic_version={current!r}; expected {head!r}. '
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
