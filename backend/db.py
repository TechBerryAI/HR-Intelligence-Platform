"""
PostgreSQL database adapter for HR Job Portal.
Uses psycopg (v3); parameters use %s placeholders (callers may pass ? and they are converted).
"""
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
                            print(f"[DB WARNING] Could not pre-populate connection: {e}")
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

    # Ensure is_super_admin column exists on hr_signup (idempotent)
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = current_schema() AND table_name = 'hr_signup' AND column_name = 'is_super_admin'
                """)
                if cursor.fetchone() is None:
                    cursor.execute("ALTER TABLE hr_signup ADD COLUMN is_super_admin BOOLEAN DEFAULT false")
                    print("[DB] Added column hr_signup.is_super_admin")
    except Exception as e:
        print(f"[DB] Warning ensuring is_super_admin column: {e}")

    # Seed default super admin user if not present (idempotent)
    _seed_super_admin_if_missing()


def _seed_super_admin_if_missing():
    """Create default super admin in hr_signup if no user with that email exists. Uses env for credentials."""
    seed_email = (os.getenv('SUPER_ADMIN_SEED_EMAIL') or 'unmesh.tari@techberry.com').strip().lower()
    seed_password = (os.getenv('SUPER_ADMIN_SEED_PASSWORD') or 'Unmeshtari@123').strip()
    seed_name = (os.getenv('SUPER_ADMIN_SEED_FULL_NAME') or 'Super Administrator').strip()
    seed_company = (os.getenv('SUPER_ADMIN_SEED_COMPANY') or 'Techberry').strip()
    if not seed_email or not seed_password:
        return
    try:
        existing = db_get('SELECT hrid FROM hr_signup WHERE LOWER(email) = ?', (seed_email,))
        if existing:
            # Ensure existing user is marked super admin
            db_run('UPDATE hr_signup SET is_super_admin = true WHERE LOWER(email) = ?', (seed_email,))
            return
        import bcrypt
        password_hash = bcrypt.hashpw(seed_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        row = db_get('SELECT COALESCE(MAX(CAST(SUBSTRING(hrid FROM 5) AS INT)), 0) AS maxn FROM hr_signup WHERE hrid ~ ?', ('^HRID[0-9]+$',))
        next_num = int(row['maxn']) + 1 if row and row.get('maxn') is not None else 1
        hrid = f"HRID{next_num:03d}"
        db_run(
            'INSERT INTO hr_signup (hrid, full_name, email, company, password, is_super_admin) VALUES (?, ?, ?, ?, ?, true)',
            (hrid, seed_name or seed_email, seed_email, seed_company or '-', password_hash),
        )
        print(f"[DB] Seeded super admin user: {seed_email}")
    except Exception as e:
        print(f"[DB] Warning seeding super admin: {e}")


def init_db():
    """Apply schema from schema_pg/01_schema.sql (idempotent)."""
    run_migrations()
