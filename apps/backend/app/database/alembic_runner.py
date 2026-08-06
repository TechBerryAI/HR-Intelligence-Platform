"""Run Alembic migrations — primary schema manager for HCIP."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_BASELINE = '20260806_0001'


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


def repair_orphan_stamp() -> bool:
    """
    If alembic_version points at a deleted revision (e.g. empty stub),
    retarget to baseline so upgrade head can continue.
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
    if current in known:
        return False

    logger.warning(
        '[alembic] orphan stamp %s not in scripts; retargeting to %s',
        current,
        _BASELINE,
    )
    print(f'[DB] Alembic orphan stamp {current} → {_BASELINE}')
    db_run(
        'UPDATE alembic_version SET version_num = %s WHERE version_num = %s',
        (_BASELINE, current),
    )
    # Ensure stamp matches even if UPDATE affected 0 rows somehow
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


def stamp_if_needed() -> None:
    """
    If the DB already has application tables but no alembic_version row,
    stamp at baseline so upgrade can apply later revisions.
    Also repairs orphan stamps from deleted revision files.
    """
    from alembic import command
    from app.database.connection.db import db_get

    if repair_orphan_stamp():
        return

    has_apps = db_get(
        """
        SELECT 1 AS ok
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'applications'
        """,
        (),
    )
    if not has_apps:
        return

    has_version = db_get(
        """
        SELECT 1 AS ok
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'alembic_version'
        """,
        (),
    )
    if has_version:
        ver = db_get('SELECT version_num FROM alembic_version LIMIT 1', ())
        if ver and ver.get('version_num'):
            return

    command.stamp(_config(), _BASELINE)
    logger.info('[alembic] stamped existing DB at %s', _BASELINE)
    print(f'[DB] Alembic stamped at {_BASELINE} (legacy DB)')
