"""Alembic environment — uses the same Postgres URL as the Flask app."""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool, text

# apps/backend on sys.path
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dotenv import load_dotenv

load_dotenv(_BACKEND / '.env')
os.environ['HCIP_PROCESS_ROLE'] = 'migrate'

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Domain uses raw SQL primarily; metadata is optional for autogenerate later.
target_metadata = None
try:
    from app.domains.identity.models import Base

    target_metadata = Base.metadata
except Exception:
    target_metadata = None


def _database_url() -> str:
    url = (os.getenv('DATABASE_URL') or '').strip()
    if not url:
        from urllib.parse import quote_plus

        host = os.getenv('POSTGRES_HOST', os.getenv('PGHOST', 'localhost'))
        port = os.getenv('POSTGRES_PORT', os.getenv('PGPORT', '5432'))
        db = os.getenv('POSTGRES_DB', os.getenv('PGDATABASE', 'JobPortal'))
        user = os.getenv('POSTGRES_USER', os.getenv('PGUSER', 'postgres'))
        password = os.getenv('POSTGRES_PASSWORD', os.getenv('PGPASSWORD', ''))
        url = (
            f'postgresql://{quote_plus(user)}:{quote_plus(password)}'
            f'@{host}:{port}/{db}'
        )
    # SQLAlchemy 2 + psycopg3
    if url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://') :]
    elif url.startswith('postgres://'):
        url = 'postgresql+psycopg://' + url[len('postgres://') :]
    return url


def _repair_orphan_stamp(connection) -> None:
    """Retarget alembic_version only for allowlisted deleted revisions (dev)."""
    from sqlalchemy import text, inspect
    from alembic.script import ScriptDirectory

    from app.database.alembic_runner import orphan_stamp_action

    try:
        insp = inspect(connection)
        if not insp.has_table('alembic_version'):
            return
        row = connection.execute(
            text('SELECT version_num FROM alembic_version LIMIT 1')
        ).fetchone()
    except Exception as exc:
        # Never rollback the Alembic migration transaction on a missing table.
        print(f'[alembic] orphan-stamp check skipped: {exc}')
        return

    if not row or not row[0]:
        return

    current = row[0]
    known = {rev.revision for rev in ScriptDirectory.from_config(config).walk_revisions()}
    action = orphan_stamp_action(current, known)
    if action != 'repair':
        return

    from app.database.alembic_runner import _BASELINE

    print(f'[alembic] orphan stamp {current} → {_BASELINE}')
    connection.execute(
        text(
            'UPDATE alembic_version SET version_num = :v WHERE version_num = :old'
        ),
        {'v': _BASELINE, 'old': current},
    )
    # Do not commit here — stay inside the Alembic migration transaction.


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from app.database.alembic_runner import MIGRATION_ADVISORY_LOCK_KEY
    from app.database.connection.db import postgres_application_name

    configuration = config.get_section(config.config_ini_section) or {}
    configuration['sqlalchemy.url'] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
        connect_args={'application_name': postgres_application_name()},
    )
    with connectable.connect() as connection:
        locked = False
        try:
            connection.execute(text("SET lock_timeout = '120s'"))
            connection.execute(
                text('SELECT pg_advisory_lock(:k)'),
                {'k': MIGRATION_ADVISORY_LOCK_KEY},
            )
            connection.commit()
            locked = True
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                transaction_per_migration=True,
            )
            with context.begin_transaction():
                _repair_orphan_stamp(connection)
                context.run_migrations()
            try:
                connection.commit()
            except Exception:
                pass
        finally:
            if locked:
                try:
                    connection.execute(
                        text('SELECT pg_advisory_unlock(:k)'),
                        {'k': MIGRATION_ADVISORY_LOCK_KEY},
                    )
                    connection.commit()
                except Exception:
                    pass


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
