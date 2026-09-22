"""Synchronization schema is registered and produces PostgreSQL migration SQL."""

from io import StringIO
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.db.base import Base
from app.models import SyncJob


def test_sync_job_has_requested_columns_and_nullable_timestamps():
    table = SyncJob.__table__
    assert Base.metadata.tables["sync_jobs"] is table
    assert set(table.columns.keys()) == {
        "id",
        "status",
        "started_at",
        "completed_at",
        "files_scanned",
        "files_imported",
        "files_skipped",
        "errors",
    }
    assert table.c.started_at.nullable and table.c.completed_at.nullable
    assert not table.c.errors.nullable
    assert table.c.started_at.type.timezone and table.c.completed_at.type.timezone


def test_sync_job_migration_offline_has_guards():
    output = StringIO()
    config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output
    )
    command.upgrade(config, "0004_asset_soft_delete:0005_sync_jobs", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE sync_jobs" in sql
    assert "ck_sync_jobs_counters_consistent" in sql
    assert "ck_sync_jobs_lifecycle_valid" in sql
    assert "ck_sync_jobs_errors_array" in sql
    assert "DROP TABLE assets" not in sql
