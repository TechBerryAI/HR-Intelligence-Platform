"""Run Alembic migrations — sole schema manager for HCIP."""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_BASELINE = '20260810_s001'


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
    If alembic_version points at a deleted revision, retarget to baseline
    so ``upgrade head`` can continue (local/dev wipe-or-restamp path).
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
