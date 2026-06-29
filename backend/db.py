"""
PostgreSQL database adapter for HR Job Portal.
Uses psycopg (v3); parameters use %s placeholders (callers may pass ? and they are converted).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from queue import Queue, Empty
import threading
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

BACKEND = "postgresql"
NOW_SQL = "NOW()"
TRUE_SQL = "true"
FALSE_SQL = "false"

# PostgreSQL connection: prefer DATABASE_URL, else build from POSTGRES_* env
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', os.getenv('PGHOST', 'localhost'))
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', os.getenv('PGPORT', '5432')))
    POSTGRES_DB = os.getenv('POSTGRES_DB', os.getenv('PGDATABASE', 'JobPortal'))
    POSTGRES_USER = os.getenv('POSTGRES_USER', os.getenv('PGUSER', 'postgres'))
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', os.getenv('PGPASSWORD', ''))
    safe_user = quote_plus(POSTGRES_USER)
    safe_pass = quote_plus(POSTGRES_PASSWORD)
    DATABASE_URL = f"postgresql://{safe_user}:{safe_pass}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

DB_TARGET = (
    f"{os.getenv('POSTGRES_HOST', os.getenv('PGHOST', 'localhost'))}:"
    f"{os.getenv('POSTGRES_PORT', os.getenv('PGPORT', '5432'))}/"
    f"{os.getenv('POSTGRES_DB', os.getenv('PGDATABASE', 'postgres'))}"
)

POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
CONNECTION_TIMEOUT = int(os.getenv('DB_CONNECTION_TIMEOUT', '10'))

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


def _create_connection():
    if psycopg is None:
        raise RuntimeError("psycopg is required for PostgreSQL. Install with: pip install psycopg[binary]")
    return psycopg.connect(DATABASE_URL, connect_timeout=CONNECTION_TIMEOUT)


class ConnectionPool:
    def __init__(self, pool_size=5):
        self.pool_size = pool_size
        self.pool = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self._initialized = False

    def _create_connection(self):
        return _create_connection()

    def get_connection(self, timeout=5):
        if not self._initialized:
            with self.lock:
                if not self._initialized:
                    print(f"[DB] Initializing connection pool with {self.pool_size} connections...")
                    for _ in range(self.pool_size):
                        try:
                            conn = self._create_connection()
                            self.pool.put(conn)
                        except Exception as e:
                            print(f"[DB WARNING] Could not pre-populate connection to {DB_TARGET}: {e}")
                self._initialized = True
        try:
            conn = self.pool.get(timeout=timeout)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                return self._create_connection()
        except Empty:
            return self._create_connection()

    def return_connection(self, conn):
        try:
            if self.pool.qsize() < self.pool_size:
                self.pool.put_nowait(conn)
            else:
                conn.close()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass


_connection_pool = ConnectionPool(pool_size=POOL_SIZE)


@contextmanager
def get_conn():
    conn = None
    try:
        conn = _connection_pool.get_connection()
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            _connection_pool.return_connection(conn)


def rows_to_dicts(cursor, rows):
    if not rows:
        return []
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def _pg_query(query: str):
    """Convert ? placeholders to %s for psycopg."""
    return query.replace("?", "%s")


def db_run(query: str, params: list | tuple = ()):
    """Execute query; returns {lastID, changes}. For INSERT ... RETURNING id, lastID is set from returned row."""
    query = _pg_query(query)
    with get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            changes = cursor.rowcount
            last_id = None
            if "RETURNING" in query.upper():
                row = cursor.fetchone()
                if row:
                    last_id = row[0] if isinstance(row, (list, tuple)) else (row.get("id") if isinstance(row, dict) else row)
                    if last_id is not None:
                        last_id = int(last_id)
            return {"lastID": last_id, "changes": changes}


def db_get(query: str, params: list | tuple = ()):
    query = _pg_query(query)
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None


def db_all(query: str, params: list | tuple = ()):
    query = _pg_query(query)
    with get_conn() as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows] if rows else []


def _split_sql_statements(sql: str):
    """Split SQL by ; but keep DO $$ ... END $$; as a single statement."""
    sql = sql.strip()
    if not sql:
        return []
    # If file contains a DO $$ block, run it as a single statement (no split)
    if 'DO $$' in sql or 'do $$' in sql.lower():
        return [sql] if sql.endswith(';') else [sql + ';']
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    return [s + ';' if not s.endswith(';') else s for s in statements]


def run_migrations():
    """Run PostgreSQL schema from backend/schema_pg: 01_schema.sql then 02_*.sql, 03_*.sql, ... in order."""
    schema_dir = os.path.join(os.path.dirname(__file__), 'schema_pg')
    if not os.path.isdir(schema_dir):
        return
    import glob
    sql_files = sorted(glob.glob(os.path.join(schema_dir, '*.sql')))
    for schema_file in sql_files:
        with open(schema_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        lines = []
        for line in sql.splitlines():
            stripped = line.strip()
            if stripped.startswith('--') or not stripped:
                continue
            lines.append(line)
        sql_clean = '\n'.join(lines)
        # Split into statements; keep DO $$ ... END $$; blocks as one statement
        statements = _split_sql_statements(sql_clean)
        with get_conn() as conn:
            with conn.cursor() as cursor:
                for stmt in statements:
                    try:
                        cursor.execute(stmt)
                    except Exception as e:
                        if 'already exists' not in str(e).lower() and 'duplicate' not in str(e).lower():
                            print(f"[DB] Migration warning in {os.path.basename(schema_file)}: {e}")
                        conn.rollback()

    # Ensure role column exists on hr_signup (idempotent)
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema() AND table_name = 'hr_signup' AND column_name = 'role'
                """)
                if cursor.fetchone() is None:
                    cursor.execute("""
                        ALTER TABLE hr_signup ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'RECRUITER'
                    """)
                    print("[DB] Added column hr_signup.role")
    except Exception as e:
        print(f"[DB] Warning ensuring role column: {e}")

    # Admin accounts are seeded via schema_pg/06_seed_admin_accounts.sql and 07_seed_ceo_account.sql


def init_db():
    """Apply schema from schema_pg/01_schema.sql (idempotent)."""
    run_migrations()
