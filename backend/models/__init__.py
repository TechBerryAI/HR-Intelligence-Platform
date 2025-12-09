import os
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Load .env file BEFORE building connection URI
load_dotenv()


def _build_connection_uri() -> str:
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


engine = create_engine(
    _build_connection_uri(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=10,  # Wait max 10s for connection from pool
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={"timeout": 10},  # SQL Server connection timeout
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

