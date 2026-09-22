"""PostgreSQL enforces sync counters, lifecycle, defaults and migration parity."""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.models import SyncJob

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"
    ),
]


def test_defaults_and_run_lifecycle(migrated_database):
    engine, config = migrated_database
    with Session(engine) as session:
        first, second = SyncJob(), SyncJob()
        session.add_all([first, second])
        session.commit()
        assert first.id != second.id and first.status == "pending"
        assert first.errors == second.errors == []
        assert first.started_at is first.completed_at is None
        assert first.files_scanned == first.files_imported == first.files_skipped == 0
        first.status = "running"
        first.started_at = datetime.now(UTC)
        session.commit()
        first.files_scanned = 3
        first.files_imported = 1
        first.files_skipped = 1
        first.errors.append({"code": "download_unavailable", "file_id": "example-id"})
        first.status = "completed_with_errors"
        first.completed_at = datetime.now(UTC)
        session.commit()
        session.expire_all()
        assert first.errors == [
            {"code": "download_unavailable", "file_id": "example-id"}
        ]
        assert second.errors == []
        assert first.completed_at >= first.started_at
    command.check(config)


@pytest.mark.parametrize(
    "values",
    [
        {"status": "unknown"},
        {"files_scanned": -1},
        {"files_imported": -1},
        {"files_skipped": -1},
        {"files_imported": 1},
        {"files_scanned": 1, "files_skipped": 2},
        {"status": "running"},
        {"status": "completed"},
        {"status": "failed"},
        {"status": "pending", "started_at": datetime(2026, 1, 1, tzinfo=UTC)},
        {
            "status": "running",
            "started_at": datetime(2026, 1, 1, tzinfo=UTC),
            "completed_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
        {
            "status": "completed",
            "started_at": datetime(2026, 1, 2, tzinfo=UTC),
            "completed_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
    ],
)
def test_invalid_state_rejected_by_database(migrated_database, values):
    engine, _ = migrated_database
    with Session(engine) as session:
        session.add(SyncJob(**values))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_database_defaults_and_error_array_constraint(migrated_database):
    engine, _ = migrated_database
    identifier = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO sync_jobs (id) VALUES (:id)"), {"id": identifier}
        )
    with Session(engine) as session:
        record = session.get(SyncJob, identifier)
        assert record.status == "pending" and record.errors == []
    with engine.connect() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text("UPDATE sync_jobs SET errors = '{}'::jsonb"))
        connection.rollback()


@pytest.mark.parametrize("status", ["completed", "completed_with_errors", "failed"])
def test_terminal_states_have_timezone_aware_timestamps(migrated_database, status):
    engine, _ = migrated_database
    start = datetime.now(UTC)
    with Session(engine) as session:
        session.add(
            SyncJob(
                status=status,
                started_at=start,
                completed_at=start + timedelta(seconds=1),
            )
        )
        session.commit()
        job = session.scalars(select(SyncJob)).one()
        assert job.started_at.tzinfo is not None and job.completed_at.tzinfo is not None


def test_migration_roundtrip_keeps_registry_tables(migrated_database):
    engine, config = migrated_database
    assert "sync_jobs" in inspect(engine).get_table_names()
    command.downgrade(config, "0004_asset_soft_delete")
    tables = inspect(engine).get_table_names()
    assert "sync_jobs" not in tables
    assert "assets" in tables and "drive_imports" in tables
    command.upgrade(config, "head")
    command.check(config)
