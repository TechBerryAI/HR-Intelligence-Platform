"""Apply consolidated schema_pg SQL files (idempotent)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = _BACKEND_ROOT / 'schema_pg'

SCHEMA_FILES = (
    '01_core.sql',
    '02_domain.sql',
    '03_integrations.sql',
    '04_seeds.sql',
)

_BENIGN = (
    'already exists',
    'duplicate',
    'does not exist',
)


def _split_sql_statements(sql: str) -> list[str]:
    """
    Split on ``;`` outside PostgreSQL dollar-quoted strings (``$$`` / ``$tag$``).
    Handles both ``DO $$ … END $$;`` and ``CREATE FUNCTION … AS $$ … $$;``.
    """
    sql = sql.strip()
    if not sql:
        return []

    statements: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(sql)
    dollar_tag: str | None = None

    while i < n:
        if dollar_tag is None:
            # Line comment
            if sql.startswith('--', i):
                eol = sql.find('\n', i)
                if eol == -1:
                    break
                i = eol + 1
                continue
            # Start of dollar-quote: $$ or $tag$
            if sql[i] == '$':
                m = re.match(r'\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$', sql[i:])
                if m:
                    dollar_tag = m.group(0)
                    buf.append(dollar_tag)
                    i += len(dollar_tag)
                    continue
            if sql[i] == ';':
                buf.append(';')
                stmt = ''.join(buf).strip()
                if stmt:
                    statements.append(stmt)
                buf = []
                i += 1
                continue
            buf.append(sql[i])
            i += 1
            continue

        # Inside dollar-quoted string: look for matching closer
        if sql.startswith(dollar_tag, i):
            buf.append(dollar_tag)
            i += len(dollar_tag)
            dollar_tag = None
            continue
        buf.append(sql[i])
        i += 1

    rem = ''.join(buf).strip()
    if rem:
        if not rem.endswith(';'):
            rem += ';'
        statements.append(rem)
    return statements


def _is_benign(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(x in msg for x in _BENIGN)


def apply_sql_text(connection, sql: str, *, source: str = '') -> None:
    """
    Execute SQL on a SQLAlchemy Connection (Alembic) or psycopg connection.
    Benign 'already exists' / 'does not exist' errors are skipped via SAVEPOINT.
    """
    from sqlalchemy import text
    from sqlalchemy.engine import Connection as SAConnection

    statements = _split_sql_statements(sql)
    if isinstance(connection, SAConnection):
        for stmt in statements:
            try:
                connection.execute(text('SAVEPOINT hcip_schema_sp'))
                # Driver SQL avoids SQLAlchemy bind parsing of :tokens / ::casts in DDL
                connection.exec_driver_sql(stmt)
                connection.execute(text('RELEASE SAVEPOINT hcip_schema_sp'))
            except Exception as e:
                try:
                    connection.execute(text('ROLLBACK TO SAVEPOINT hcip_schema_sp'))
                except Exception:
                    pass
                if _is_benign(e):
                    continue
                logger.error('[schema] %s failed: %s\n---\n%s\n---', source, e, stmt[:500])
                raise
        return

    # psycopg connection
    for stmt in statements:
        try:
            with connection.cursor() as cursor:
                cursor.execute(stmt)
        except Exception as e:
            if hasattr(connection, 'rollback'):
                connection.rollback()
            if _is_benign(e):
                continue
            logger.error('[schema] %s failed: %s\n---\n%s\n---', source, e, stmt[:500])
            raise


def apply_consolidated_schema(connection=None) -> None:
    """Apply schema_pg 01–04 in order. Uses app pool when connection is None."""
    if not SCHEMA_DIR.is_dir():
        raise FileNotFoundError(f'schema_pg missing: {SCHEMA_DIR}')

    def _run(conn):
        for name in SCHEMA_FILES:
            path = SCHEMA_DIR / name
            if not path.is_file():
                raise FileNotFoundError(path)
            logger.info('[schema] applying %s', name)
            print(f'[DB] Applying {name}…')
            apply_sql_text(conn, path.read_text(encoding='utf-8'), source=name)

    if connection is not None:
        _run(connection)
        return

    from app.database.connection.db import get_conn

    with get_conn() as conn:
        _run(conn)

    _ensure_hr_role_column()


def _ensure_hr_role_column() -> None:
    from app.database.connection.db import get_conn

    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = 'hr_signup' AND column_name = 'role'
                    """
                )
                if cursor.fetchone() is None:
                    cursor.execute(
                        """
                        ALTER TABLE hr_signup
                        ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'RECRUITER'
                        """
                    )
                    print('[DB] Added column hr_signup.role')
    except Exception as e:
        print(f'[DB] Warning ensuring role column: {e}')
