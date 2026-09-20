"""Application-owned PostgreSQL engine and request-scoped sessions."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def database_url(settings: Settings) -> URL:
    """Build a psycopg URL without interpolating or logging credentials."""
    return URL.create(
        "postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


def create_database_engine(settings: Settings) -> Engine:
    """Create a lazy pool; no connection is opened until first use."""
    return create_engine(
        database_url(settings),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=10,
        connect_args={"connect_timeout": 3},
        hide_parameters=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Keep objects usable after an explicit commit, without autoflush."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    """Yield one session; callers commit explicitly, failures roll back."""
    factory: sessionmaker[Session] = request.app.state.session_factory
    with factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
