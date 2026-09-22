"""PostgreSQL provenance, deduplication and parent retention guarantees."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.api.assets.repository import AssetRepository
from app.api.assets.service import AssetService
from app.models import Asset, AssetImport, SyncJob

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"
    ),
]


def parents(session):
    asset = Asset(
        name="Source footage",
        storage_uri="s3://wwml/source.mp4",
        media_type="video",
        mime_type="video/mp4",
        size_bytes=10,
        sha256="a" * 64,
    )
    job = SyncJob(status="running", started_at=datetime.now(UTC))
    session.add_all([asset, job])
    session.commit()
    return asset, job


def record(asset, job, **changes):
    return AssetImport(
        **(
            dict(
                asset_id=asset.id,
                google_drive_file_id="Drive-file_1",
                checksum=asset.sha256,
                sync_job_id=job.id,
            )
            | changes
        )
    )


def test_provenance_roundtrip_and_timestamp_default(migrated_database):
    engine, config = migrated_database
    with Session(engine) as session:
        asset, job = parents(session)
        imported = record(asset, job)
        session.add(imported)
        session.commit()
        session.expire_all()
        loaded = session.scalars(select(AssetImport)).one()
        assert loaded.asset_id == asset.id and loaded.sync_job_id == job.id
        assert loaded.checksum == asset.sha256
        assert loaded.import_date.tzinfo is not None
    command.check(config)


def test_same_source_same_run_cannot_be_recorded_twice(migrated_database):
    engine, _ = migrated_database
    with Session(engine) as session:
        asset, job = parents(session)
        session.add(record(asset, job))
        session.commit()
        session.add(record(asset, job))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_later_runs_and_equivalent_sources_retain_history(migrated_database):
    engine, _ = migrated_database
    with Session(engine) as session:
        asset, first = parents(session)
        second = SyncJob(status="running", started_at=datetime.now(UTC))
        session.add(second)
        session.commit()
        session.add_all(
            [
                record(asset, first),
                record(asset, second),
                record(asset, first, google_drive_file_id="another-source"),
            ]
        )
        session.commit()
        assert session.scalar(select(func.count()).select_from(AssetImport)) == 3
        assert session.scalar(select(func.count()).select_from(Asset)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"checksum": "A" * 64},
        {"checksum": "bad"},
        {"checksum": "g" * 64},
        {"google_drive_file_id": ""},
        {"google_drive_file_id": "../file"},
        {"google_drive_file_id": "file id"},
        {"asset_id": uuid4()},
        {"sync_job_id": uuid4()},
    ],
)
def test_invalid_values_or_missing_parents_rejected(migrated_database, changes):
    engine, _ = migrated_database
    with Session(engine) as session:
        asset, job = parents(session)
        session.add(record(asset, job, **changes))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


@pytest.mark.parametrize("parent", ["assets", "sync_jobs"])
def test_hard_delete_of_referenced_parents_is_restricted(migrated_database, parent):
    engine, _ = migrated_database
    with Session(engine) as session:
        asset, job = parents(session)
        session.add(record(asset, job))
        session.commit()
        identifier = asset.id if parent == "assets" else job.id
        # Table name comes only from the fixed test parameter list.
        with pytest.raises(IntegrityError):
            session.execute(
                text(f"DELETE FROM {parent} WHERE id = :id"), {"id": identifier}
            )
            session.commit()
        session.rollback()


def test_registry_soft_delete_preserves_import_history(migrated_database):
    engine, _ = migrated_database
    with Session(engine, expire_on_commit=False) as session:
        asset, job = parents(session)
        session.add(record(asset, job))
        session.commit()
        AssetService(AssetRepository(session)).delete(asset.id)
        imported = session.scalars(select(AssetImport)).one()
        assert imported.asset_id == asset.id
        assert imported.sync_job_id == job.id
        assert asset.deleted_at is not None
        assert imported.checksum == "a" * 64


def test_checksum_is_historical_snapshot(migrated_database):
    engine, _ = migrated_database
    with Session(engine) as session:
        asset, job = parents(session)
        session.add(record(asset, job))
        session.commit()
        asset.sha256 = "b" * 64
        session.commit()
        assert session.scalars(select(AssetImport)).one().checksum == "a" * 64


def test_downgrade_preserves_parent_records(migrated_database):
    engine, config = migrated_database
    with Session(engine) as session:
        asset, job = parents(session)
        session.add(record(asset, job))
        session.commit()
    command.downgrade(config, "0005_sync_jobs")
    assert "asset_imports" not in inspect(engine).get_table_names()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 1
        assert session.scalar(select(func.count()).select_from(SyncJob)) == 1
    command.upgrade(config, "head")
    command.check(config)
