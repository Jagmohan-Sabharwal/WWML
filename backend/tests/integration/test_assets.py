"""Real PostgreSQL migration and persistence checks against a disposable database."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.db.session import create_database_engine
from app.models import Asset

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_DB_TESTS") != "1",
        reason="Requires RUN_DB_TESTS=1 and a disposable PostgreSQL _test database",
    ),
]
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


def new_asset(**overrides: object) -> Asset:
    values: dict[str, object] = {
        "name": "Interview master",
        "storage_uri": "gs://wwml-test/interview.mov",
        "media_type": "video",
        "mime_type": "video/quicktime",
        "size_bytes": 1024,
        "sha256": "a" * 64,
    }
    return Asset(**(values | overrides))


def test_upgrade_downgrade_upgrade_and_metadata_match(
    migrated_database: tuple[Engine, Config],
) -> None:
    engine, config = migrated_database
    assert "assets" in inspect(engine).get_table_names()
    command.check(config)
    command.downgrade(config, "base")
    assert "assets" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)


def test_asset_round_trip_defaults_and_explicit_update(
    migrated_database: tuple[Engine, Config],
) -> None:
    engine, _ = migrated_database
    with Session(engine) as session:
        asset = new_asset(asset_metadata={"duration_seconds": 90})
        session.add(asset)
        session.commit()
        asset_id = asset.id
        created = asset.created_at
        assert asset.created_at.tzinfo is not None
        assert asset.updated_at.tzinfo is not None
        asset.description = "Reusable interview footage"
        session.commit()
        session.refresh(asset)
        assert asset.updated_at >= created
    with Session(engine) as session:
        loaded = session.scalar(select(Asset).where(Asset.id == asset_id))
        assert loaded is not None
        assert loaded.asset_metadata == {"duration_seconds": 90}
        assert loaded.description == "Reusable interview footage"


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"size_bytes": -1}, "ck_assets_size_nonnegative"),
        ({"sha256": "not-a-hash"}, "ck_assets_sha256_format"),
        ({"name": "  "}, "ck_assets_name_nonempty"),
        ({"storage_uri": " "}, "ck_assets_storage_uri_nonempty"),
        ({"media_type": "unknown"}, "ck_assets_media_type_valid"),
    ],
)
def test_invalid_assets_rejected_by_postgres(
    migrated_database: tuple[Engine, Config],
    overrides: dict[str, object],
    constraint: str,
) -> None:
    engine, _ = migrated_database
    with Session(engine) as session:
        session.add(new_asset(**overrides))
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert error.value.orig.diag.constraint_name == constraint
        session.rollback()


def test_identical_file_cannot_be_registered_twice(
    migrated_database: tuple[Engine, Config],
) -> None:
    engine, _ = migrated_database
    with Session(engine) as session:
        original = new_asset()
        session.add(original)
        session.commit()
        assert original.asset_metadata == {}
        session.add(new_asset(storage_uri="gs://wwml-test/copy.mov"))
        with pytest.raises(IntegrityError) as error:
            session.commit()
        assert error.value.orig.diag.constraint_name == "uq_assets_sha256"
        session.rollback()
        assert len(session.scalars(select(Asset)).all()) == 1
