import os
from contextlib import contextmanager
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()


def _build_connection_uri() -> str:
    database_url = (os.getenv('DATABASE_URL') or '').strip()
    if database_url and database_url.lower().startswith('postgresql://'):
        uri = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    else:
        host = os.getenv('POSTGRES_HOST', os.getenv('PGHOST', 'localhost'))
        port = os.getenv('POSTGRES_PORT', os.getenv('PGPORT', '5432'))
        db = os.getenv('POSTGRES_DB', os.getenv('PGDATABASE', 'JobPortal'))
        user = os.getenv('POSTGRES_USER', os.getenv('PGUSER', 'postgres'))
        password = os.getenv('POSTGRES_PASSWORD', os.getenv('PGPASSWORD', ''))
        uri = f"postgresql+psycopg://{user}:{quote_plus(password)}@{host}:{port}/{db}"
    print("[SQLAlchemy] Using PostgreSQL")
    return uri


_uri = _build_connection_uri()
engine = create_engine(
    _uri,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=10,
    pool_recycle=3600,
    connect_args={"connect_timeout": 10},
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
