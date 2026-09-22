"""Asset provenance metadata and offline migration contract."""

from io import StringIO
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.db.base import Base
from app.models import AssetImport


def test_requested_fields_and_parent_references():
    table = AssetImport.__table__
    assert Base.metadata.tables["asset_imports"] is table
    assert set(table.columns.keys()) == {
        "asset_id",
        "google_drive_file_id",
        "checksum",
        "import_date",
        "sync_job_id",
    }
    assert all(not column.nullable for column in table.columns)
    assert {column.name for column in table.primary_key.columns} == {
        "sync_job_id",
        "google_drive_file_id",
    }
    assert {key.target_fullname for key in table.foreign_keys} == {
        "assets.id",
        "sync_jobs.id",
    }
    assert all(key.ondelete == "RESTRICT" for key in table.foreign_keys)
    assert table.c.import_date.type.timezone is True


def test_offline_migration_creates_only_provenance_table():
    output = StringIO()
    config = Config(
        str(Path(__file__).resolve().parents[1] / "alembic.ini"),
        output_buffer=output,
    )
    command.upgrade(config, "0005_sync_jobs:0006_asset_imports", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE asset_imports" in sql
    assert "ck_asset_imports_checksum_format" in sql
    assert "ck_asset_imports_drive_file_id_format" in sql
    assert sql.count("ON DELETE RESTRICT") == 2
    assert "DROP TABLE" not in sql
