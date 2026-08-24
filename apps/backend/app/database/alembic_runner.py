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

# Stamps from unmerged local work (never committed migration scripts).
# Dev/debug may retarget to the canonical revision when schema already matches.
# Production never rewrites alembic_version for these.
_PHANTOM_STAMP_REPAIRS: dict[str, str] = {
    '20260824_bulk_pause': '20260814_cid_pad3',
}


class AlembicOrphanStampError(RuntimeError):
    """alembic_version points at a revision this process cannot apply."""


class SchemaNotAtHeadError(RuntimeError):
    """Database alembic_version is missing or not equal to this tree's head."""


class SchemaMigrationPolicyError(RuntimeError):
    """Production web/worker tried to migrate or started without the skip flag."""


_PROD_MIGRATE_INSTRUCTIONS = (
    "Production web processes must not run migrations.\n"
    "1. cd apps/backend && HCIP_PROCESS_ROLE=migrate alembic upgrade head\n"
    "2. alembic current   # must equal alembic heads\n"
    "3. MIGRATIONS_ALREADY_APPLIED=true gunicorn -c gunicorn.conf.py wsgi:app"
)


def _is_production_like() -> bool:
    return os.getenv('FLASK_DEBUG', 'false').lower() != 'true'


def _truthy_env(name: str) -> bool:
    return (os.getenv(name) or '').strip().lower() in ('1', 'true', 'yes', 'on')


def migrations_already_applied() -> bool:
    """Operator flag (or Gunicorn inherited skip) — verify only, never upgrade."""
    if _truthy_env('MIGRATIONS_ALREADY_APPLIED'):
        return True
    return os.getenv('HCIP_MIGRATIONS_DONE') == '1'


def production_web_must_not_migrate() -> bool:
    from app.config.env_validator import is_production_like

    return is_production_like()


def head_revision_ids() -> list[str]:
    from alembic.script import ScriptDirectory

    return list(ScriptDirectory.from_config(_config()).get_heads())


def schema_at_head_status(current: str | None, heads: list[str]) -> str:
    """Return the single head id, or raise if current is not exactly that head."""
    if len(heads) != 1:
        raise SchemaNotAtHeadError(
            f"Expected a single Alembic head, found {heads!r}. "
            "Resolve multiple heads before starting the application."
        )
    head = heads[0]
    if not current:
        raise SchemaNotAtHeadError(
            f"alembic_version is empty or missing; expected head {head!r}. "
            "Run: HCIP_PROCESS_ROLE=migrate alembic upgrade head"
        )
    if current != head:
        raise SchemaNotAtHeadError(
            f"alembic current={current!r} != head={head!r}. "
            "Run: HCIP_PROCESS_ROLE=migrate alembic upgrade head"
        )
    return head


def current_revision() -> str | None:
    from app.database.connection.db import db_get

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
        return None
    ver = db_get('SELECT version_num FROM alembic_version LIMIT 1', ())
    return (ver or {}).get('version_num')


def verify_at_head() -> str:
    """Fail closed unless alembic_version equals this application's single head."""
    return schema_at_head_status(current_revision(), head_revision_ids())


def prepare_schema_for_web_process() -> str:
    """
    Production: require MIGRATIONS_ALREADY_APPLIED (or HCIP_MIGRATIONS_DONE) and
    verify at head — never upgrade. Development may run upgrade_head().
    """
    skip = migrations_already_applied()
    if production_web_must_not_migrate():
        if not skip:
            raise SchemaMigrationPolicyError(_PROD_MIGRATE_INSTRUCTIONS)
        head = verify_at_head()
        logger.info('[alembic] verified at head %s (web will not migrate)', head)
        print(f'[DB] Schema verified at head {head} (migrations already applied)')
        return head
    if skip:
        head = verify_at_head()
        print(f'[DB] Schema already applied (at head {head})')
        return head
    upgrade_head()
    head = verify_at_head()
    print('[DB] Database initialized successfully')
    return head


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
    if not production and current in _PHANTOM_STAMP_REPAIRS:
        return 'repair'
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

    target = _PHANTOM_STAMP_REPAIRS.get(current, _BASELINE)
    logger.warning(
        '[alembic] orphan stamp %s not in scripts; retargeting to %s '
        '(wipe/recreate DB if schema is incomplete)',
        current,
        target,
    )
    print(f'[DB] Alembic orphan stamp {current} → {target} (prefer wipe+upgrade for local DBs)')
    db_run(
        'UPDATE alembic_version SET version_num = %s WHERE version_num = %s',
        (target, current),
    )
    still = db_get('SELECT version_num FROM alembic_version LIMIT 1', ())
    if (still or {}).get('version_num') != target:
        command.stamp(_config(), target)
    return True


def upgrade_head() -> None:
    """Apply pending Alembic revisions (``alembic upgrade head``)."""
    from alembic import command

    repair_orphan_stamp()
    command.upgrade(_config(), 'head')
    logger.info('[alembic] upgrade head complete')
    print('[DB] Alembic upgrade head complete')
