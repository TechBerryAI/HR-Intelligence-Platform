import os
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _build_connection_uri() -> str:
    driver = os.getenv('MSSQL_ODBC_DRIVER', '{ODBC Driver 17 for SQL Server}')
    raw_conn = (
        f"DRIVER={driver};"
        f"SERVER={os.getenv('MSSQL_SERVER', 'DESKTOP-GC3KL6I')},{os.getenv('MSSQL_PORT', '1433')};"
        f"DATABASE={os.getenv('MSSQL_DATABASE', 'JobPortal')};"
        f"UID={os.getenv('MSSQL_USER', 'Test')};"
        f"PWD={os.getenv('MSSQL_PASSWORD', 'Root@123')};"
        "TrustServerCertificate=yes;"
    )
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(raw_conn)}"


engine = create_engine(
    _build_connection_uri(),
    pool_pre_ping=True,
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

