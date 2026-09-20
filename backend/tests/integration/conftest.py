"""Shared migration fixture for isolated real-PostgreSQL tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from alembic import command
from app.core.config import Settings
from app.db.session import create_database_engine

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def migrated_database() -> Iterator[tuple[Engine, Config]]:
    settings = Settings()
    if not settings.postgres_db.endswith("_test"):
        pytest.fail("Integration tests require POSTGRES_DB ending in _test")
    config = Config(str(ROOT / "alembic.ini"))
    engine = create_database_engine(settings)
    # Fail closed: never downgrade or erase an existing database.
    if inspect(engine).get_table_names():
        engine.dispose()
        pytest.fail("Integration tests require an empty disposable database")
    try:
        command.upgrade(config, "head")
        yield engine, config
    finally:
        command.downgrade(config, "base")
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()
