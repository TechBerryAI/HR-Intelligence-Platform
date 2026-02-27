import os
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Load .env file BEFORE building connection URI
load_dotenv()


def _build_connection_uri() -> str:
    database_url = (os.getenv('DATABASE_URL') or '').strip()
    if os.getenv('USE_POSTGRES') or database_url.lower().startswith('postgresql'):
        if database_url and database_url.lower().startswith('postgresql://'):
            # SQLAlchemy prefers postgresql+psycopg2://
            uri = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
        else:
            host = os.getenv('POSTGRES_HOST', os.getenv('PGHOST', 'localhost'))
            port = os.getenv('POSTGRES_PORT', os.getenv('PGPORT', '5432'))
            db = os.getenv('POSTGRES_DB', os.getenv('PGDATABASE', 'JobPortal'))
            user = os.getenv('POSTGRES_USER', os.getenv('PGUSER', 'postgres'))
            password = os.getenv('POSTGRES_PASSWORD', os.getenv('PGPASSWORD', ''))
            uri = f"postgresql+psycopg2://{user}:{quote_plus(password)}@{host}:{port}/{db}"
        print(f"[SQLAlchemy] Using PostgreSQL")
        return uri
    driver = os.getenv('MSSQL_ODBC_DRIVER', '{SQL Server}')
    server = os.getenv('MSSQL_SERVER', 'localhost')
    port = os.getenv('MSSQL_PORT', '1433')
    database = os.getenv('MSSQL_DATABASE', 'JobPortal')
    user = os.getenv('MSSQL_USER', 'Test')
    password = os.getenv('MSSQL_PASSWORD', 'Root@123')
    raw_conn = (
        f"DRIVER={driver};"
        f"SERVER={server},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )
    print(f"[SQLAlchemy] Building connection with driver: {driver}, server: {server}, database: {database}")
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(raw_conn)}"


_uri = _build_connection_uri()
_connect_args = {"connect_timeout": 10}
if _uri.startswith("postgresql"):
    _connect_args = {}
else:
    _connect_args = {"timeout": 10}  # SQL Server
engine = create_engine(
    _uri,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=10,
    pool_recycle=3600,
    connect_args=_connect_args,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)
Base = declarative_base()


def init_models():
    # Import models so SQLAlchemy is aware of mappings.
    from . import candidate_auth  # noqa: F401
    from . import hr_auth  # noqa: F401


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

