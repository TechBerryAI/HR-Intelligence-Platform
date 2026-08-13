"""Execute multi-statement SQL (Alembic baseline / migrations helpers)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_BENIGN = (
    'already exists',
    'duplicate',
    'does not exist',
)


def split_sql_statements(sql: str) -> list[str]:
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
            if sql.startswith('--', i):
                eol = sql.find('\n', i)
                if eol == -1:
                    break
                i = eol + 1
                continue
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

    statements = split_sql_statements(sql)
    if isinstance(connection, SAConnection):
        for stmt in statements:
            try:
                connection.execute(text('SAVEPOINT hcip_schema_sp'))
                connection.exec_driver_sql(stmt)
                connection.execute(text('RELEASE SAVEPOINT hcip_schema_sp'))
            except Exception as e:
                try:
                    connection.execute(text('ROLLBACK TO SAVEPOINT hcip_schema_sp'))
                except Exception:
                    pass
                if _is_benign(e):
                    continue
                logger.error('[sql] %s failed: %s\n---\n%s\n---', source, e, stmt[:500])
                raise
        return

    for stmt in statements:
        try:
            with connection.cursor() as cursor:
                cursor.execute(stmt)
        except Exception as e:
            if hasattr(connection, 'rollback'):
                connection.rollback()
            if _is_benign(e):
                continue
            logger.error('[sql] %s failed: %s\n---\n%s\n---', source, e, stmt[:500])
            raise


def apply_sql_file(connection, path: Path, *, source: str | None = None) -> None:
    text_sql = path.read_text(encoding='utf-8')
    apply_sql_text(connection, text_sql, source=source or path.name)
