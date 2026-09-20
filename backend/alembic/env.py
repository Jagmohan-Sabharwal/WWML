"""Use the same PostgreSQL settings as the API for all migrations."""

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from alembic import context
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import database_url
from app.models import Asset  # noqa: F401 -- register model metadata

settings = Settings()
configure_logging(settings.log_level)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting; credentials never enter the SQL."""
    context.configure(
        url=database_url(settings),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with one unpooled connection and explicit transactions."""
    engine = create_engine(
        database_url(settings),
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={"connect_timeout": 3},
    )
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
