"""Real PostgreSQL ingestion, migration, deduplication and recovery tests."""

import hashlib
import os
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from alembic import command
from app.api.drive.client import GoogleDriveClient
from app.api.drive.schemas import ProviderFile, ProviderPage
from app.api.imports.service import ImportService
from app.api.imports.storage import AssetStorage, ImportFailure
from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.models import Asset, DriveImport
from app.workers.drive_import import LOCK_ID, run_cycle

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"
    ),
]
CONTENT = b"documentary footage"
SHA = hashlib.sha256(CONTENT).hexdigest()


def setup_service(engine, tmp_path, *, sha=None, mime="video/mp4"):
    file = ProviderFile(
        id="source",
        name="../Interview take.mp4",
        mimeType=mime,
        size=len(CONTENT),
        version="1",
        sha256Checksum=sha,
        capabilities={"canDownload": True},
    )
    root = ProviderFile(
        id="root", name="Root", mimeType="application/vnd.google-apps.folder"
    )
    client = MagicMock(spec=GoogleDriveClient)
    client.get_folder.side_effect = lambda file_id, timeout: (
        root if file_id == "root" else file
    )
    client.list_children.return_value = ProviderPage(files=[file])
    downloader = MagicMock(return_value=[CONTENT])
    settings = Settings(_env_file=None, google_drive_folder_id="root")
    session = Session(engine, expire_on_commit=False)
    service = ImportService(
        session, client, settings, AssetStorage(tmp_path, 1000), downloader
    )
    return session, service, file, downloader


def test_register_reuse_and_changed_version(migrated_database, tmp_path):
    engine, _ = migrated_database
    session, service, file, downloader = setup_service(engine, tmp_path, sha=SHA)
    with session:
        assert service.cycle() == 1
        assert service.cycle() == 0
        asset = session.scalars(select(Asset)).one()
        assert asset.sha256 == SHA
        assert asset.asset_metadata["original_name"] == file.name
        assert asset.name.startswith("asset-Interview_take-")
        assert service.storage.root in next(tmp_path.glob("*/*.mp4")).parents
        file.version = "2"
        assert service.cycle() == 1
        assert session.scalar(select(func.count()).select_from(Asset)) == 1
        assert session.scalar(select(func.count()).select_from(DriveImport)) == 2
        assert downloader.call_count == 1


def test_reuse_after_download_without_provider_checksum(migrated_database, tmp_path):
    engine, _ = migrated_database
    session, service, file, downloader = setup_service(engine, tmp_path)
    with session:
        service.cycle()
        file.version = "2"
        service.cycle()
        assert downloader.call_count == 2
        assert session.scalar(select(func.count()).select_from(Asset)) == 1
        assert not list(service.storage.staging.iterdir())


def test_failure_retries_then_completes(migrated_database, tmp_path):
    engine, _ = migrated_database
    session, service, _, downloader = setup_service(engine, tmp_path)
    with session:
        downloader.side_effect = ImportFailure("download_unavailable")
        assert service.cycle() == 0
        job = session.scalars(select(DriveImport)).one()
        assert (job.status, job.attempts, job.error_code) == (
            "failed",
            1,
            "download_unavailable",
        )
        downloader.side_effect = None
        assert service.cycle() == 1
        assert (job.status, job.attempts, job.error_code) == ("done", 2, None)


def test_retry_limit_and_restart_of_intermediate_stage(migrated_database, tmp_path):
    engine, _ = migrated_database
    session, service, _, downloader = setup_service(engine, tmp_path)
    with session:
        downloader.side_effect = ImportFailure("download_unavailable")
        for _ in range(5):
            service.cycle()
        assert downloader.call_count == 3
        job = session.scalars(select(DriveImport)).one()
        job.attempts = 1
        job.status = "register"  # Simulate process death after publishing.
        session.commit()
        downloader.side_effect = None
        assert service.cycle() == 1
        assert job.status == "done"


@pytest.mark.parametrize(
    "failure", ["checksum", "size", "changed", "denied", "oversize"]
)
def test_integrity_failures_never_register(migrated_database, tmp_path, failure):
    engine, _ = migrated_database
    session, service, file, downloader = setup_service(engine, tmp_path)
    if failure == "checksum":
        file.sha256_checksum = "f" * 64
    elif failure == "size":
        file.size_bytes = 99
    elif failure == "denied":
        file.capabilities.can_download = False
    elif failure == "oversize":
        file.size_bytes = service.settings.import_max_bytes + 1
    elif failure == "changed":

        def changed(*args):
            file.version = "2"
            return [CONTENT]

        downloader.side_effect = changed
    with session:
        assert service.cycle() == 0
        job = session.scalars(select(DriveImport)).one()
        assert job.status == "failed"
        assert session.scalar(select(func.count()).select_from(Asset)) == 0
        assert not list(service.storage.staging.iterdir())


def test_native_files_explicitly_skipped(migrated_database, tmp_path):
    engine, _ = migrated_database
    session, service, _, downloader = setup_service(
        engine, tmp_path, mime="application/vnd.google-apps.document"
    )
    with session:
        assert service.cycle() == 0
        assert session.scalars(select(DriveImport)).one().status == "skipped"
        downloader.assert_not_called()


def test_import_progress_filter_pagination_and_deleted_asset(
    migrated_database, tmp_path
):
    engine, _ = migrated_database
    session, service, file, _ = setup_service(engine, tmp_path)
    with session:
        service.cycle()
        file.version = "2"
        service.cycle()
        asset = session.scalars(select(Asset)).one()
        session.delete(asset)
        session.commit()
    application = create_app(Settings(_env_file=None))

    def db():
        with Session(engine) as request_session:
            yield request_session

    application.dependency_overrides[get_session] = db
    with TestClient(application) as api:
        url = "/integrations/google-drive/imports"
        result = api.get(url, params={"status": "done", "page_size": 1}).json()
        assert result["total"] == 2
        assert len(result["items"]) == 1
        assert result["items"][0]["asset_id"] is None
        assert api.get(url + "/" + result["items"][0]["id"]).status_code == 200
        assert api.get(url + "/" + str(uuid4())).status_code == 404
        assert api.get(url, params={"page_size": 101}).status_code == 422
        assert api.get(url, params={"status": "bad"}).status_code == 422


def test_worker_exclusion_and_migration_roundtrip(migrated_database):
    engine, config = migrated_database
    with engine.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_ID})
        connection.commit()
        try:
            assert run_cycle(engine, Settings(_env_file=None)) == 0
        finally:
            connection.execute(
                text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID}
            )
            connection.commit()
    assert "drive_imports" in inspect(engine).get_table_names()
    command.check(config)
    command.downgrade(config, "0002_asset_discovery")
    assert "drive_imports" not in inspect(engine).get_table_names()
    assert "assets" in inspect(engine).get_table_names()
    command.upgrade(config, "head")
