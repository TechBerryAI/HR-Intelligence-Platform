"""Run Alembic migrations — sole schema manager for HCIP."""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_BASELINE = '20260810_s001'

# Session-level advisory lock so concurrent upgrade_head (Flask, scripts,
# Gunicorn without -c) cannot interleave DDL. Distinct from auto-sync lock.
MIGRATION_ADVISORY_LOCK_KEY = 872_014_002

# Deleted revisions that may still appear on local DBs after the squash.
# Production never rewrites alembic_version; debug may retarget these to baseline.
_DELETED_PRE_SQUASH = frozenset(
    {
        '20260810_0014',
        '20260811_s002',
        '20260811_s003',
        '20260811_s004',
        '20260811_s005',
    }
)


class AlembicOrphanStampError(RuntimeError):
    """alembic_version points at a revision this process cannot apply."""


def _is_production_like() -> bool:
    return os.getenv('FLASK_DEBUG', 'false').lower() != 'true'


def _config():
    from alembic.config import Config

    ini = _BACKEND_ROOT / 'alembic.ini'
    if not ini.is_file():
        raise FileNotFoundError(f'alembic.ini missing: {ini}')
    cfg = Config(str(ini))
    cfg.set_main_option('script_location', str(_BACKEND_ROOT / 'alembic'))
    return cfg


def _known_revision_ids() -> set[str]:
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_config())
    return {rev.revision for rev in script.walk_revisions()}


def orphan_stamp_action(current: str | None, known: set[str]) -> str:
    """
    Decide what to do with alembic_version.

    Returns ``ok`` (known / empty) or ``repair`` (debug + allowlisted deleted id).
    Raises AlembicOrphanStampError for unknown or production orphans.
    """
    if not current or current in known:
        return 'ok'
    production = _is_production_like()
    if production or current not in _DELETED_PRE_SQUASH:
        raise AlembicOrphanStampError(
            f"alembic_version={current!r} is not a known revision in this "
            f"application tree. Refusing to rewrite alembic_version. "
            f"Wipe/recreate the database (preferred) or run the matching "
            f"application revision. Known heads include this process's "
            f"migration scripts only."
        )
    return 'repair'


def repair_orphan_stamp() -> bool:
    """
    If alembic_version points at a deleted pre-squash revision, retarget to
    baseline so ``upgrade head`` can continue (local/dev salvage only).

    Production never rewrites the version table.
    Returns True if a repair was applied.
    """
    from alembic import command
    from app.database.connection.db import db_get, db_run

    has_version = db_get(
        """
        SELECT 1 AS ok
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'alembic_version'
        """,
        (),
    )
    if not has_version:
        return False

    ver = db_get('SELECT version_num FROM alembic_version LIMIT 1', ())
    current = (ver or {}).get('version_num')
    if not current:
        return False

    known = _known_revision_ids()
    action = orphan_stamp_action(current, known)
    if action != 'repair':
        return False

    logger.warning(
        '[alembic] orphan stamp %s not in scripts; retargeting to %s '
        '(wipe/recreate DB if schema is incomplete)',
        current,
        _BASELINE,
    )
    print(f'[DB] Alembic orphan stamp {current} → {_BASELINE} (prefer wipe+upgrade for local DBs)')
    db_run(
        'UPDATE alembic_version SET version_num = %s WHERE version_num = %s',
        (_BASELINE, current),
    )
    still = db_get('SELECT version_num FROM alembic_version LIMIT 1', ())
    if (still or {}).get('version_num') != _BASELINE:
        command.stamp(_config(), _BASELINE)
    return True


def upgrade_head() -> None:
    """Apply pending Alembic revisions (``alembic upgrade head``)."""
    from alembic import command

    repair_orphan_stamp()
    command.upgrade(_config(), 'head')
    logger.info('[alembic] upgrade head complete')
    print('[DB] Alembic upgrade head complete')
