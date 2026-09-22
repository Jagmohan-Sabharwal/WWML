"""Workspace reads against migrated PostgreSQL."""

import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.db.session import get_session
from app.main import create_app
from app.models import Asset, Production, SyncJob

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"
    ),
]


@pytest.fixture
def workspace_db(migrated_database):
    engine, config = migrated_database
    app = create_app()

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        yield client, engine, config


def test_dashboard_statistics_and_metadata(workspace_db):
    client, engine, config = workspace_db
    now = datetime.now(UTC)
    with Session(engine) as session:
        for index, (media, size, deleted) in enumerate(
            [("video", 100, None), ("audio", 30, None), ("video", 999, now)]
        ):
            session.add(
                Asset(
                    name=f"asset-{index}",
                    storage_uri=f"s3://bucket/{index}",
                    media_type=media,
                    mime_type="application/octet-stream",
                    size_bytes=size,
                    sha256=str(index) * 64,
                    deleted_at=deleted,
                )
            )
        session.add_all(
            [
                Production(name="Film"),
                Production(name="Finished", status="completed"),
                SyncJob(),
                SyncJob(status="running", started_at=now),
            ]
        )
        session.commit()
    statistics = client.get("/api/v1/assets/statistics")
    assert statistics.status_code == 200
    assert statistics.json()["total_assets"] == 2
    assert statistics.json()["total_size_bytes"] == 130
    dashboard = client.get("/api/v1/dashboard").json()
    assert dashboard["assets"] == statistics.json()
    assert dashboard["productions"]["total"] == 2
    assert dashboard["productions"]["by_status"]["completed"] == 1
    assert dashboard["sync_jobs"]["total"] == 2
    assert dashboard["sync_jobs"]["by_status"]["running"] == 1
    command.check(config)


def test_production_filter_pagination_and_ties(workspace_db):
    client, engine, _ = workspace_db
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add_all(
            [
                Production(id=UUID(int=i), name=f"Film {i}", created_at=now)
                for i in range(1, 4)
            ]
        )
        session.add(Production(name="Archive", status="archived"))
        session.commit()
    first = client.get("/api/v1/productions?status=draft&page_size=2").json()
    second = client.get("/api/v1/productions?status=draft&page_size=2&page=2").json()
    assert first["total"] == 3 and first["total_pages"] == 2
    assert [row["name"] for row in first["items"]] == ["Film 3", "Film 2"]
    assert second["items"][0]["name"] == "Film 1"
    assert first["items"][0]["updated_at"]
    assert client.get("/api/v1/productions?page=999").json()["items"] == []


def test_sync_filter_order_and_fields(workspace_db):
    client, engine, _ = workspace_db
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add_all(
            [
                SyncJob(id=UUID(int=1)),
                SyncJob(id=UUID(int=2), status="running", started_at=now),
                SyncJob(
                    id=UUID(int=3),
                    status="completed_with_errors",
                    started_at=now,
                    completed_at=now,
                    files_scanned=4,
                    files_imported=2,
                    files_skipped=1,
                    errors=[{"code": "download_failed"}],
                ),
            ]
        )
        session.commit()
    body = client.get("/api/v1/sync/jobs?page_size=2").json()
    assert body["total"] == 3
    assert [row["id"] for row in body["items"]] == [str(UUID(int=3)), str(UUID(int=2))]
    item = body["items"][0]
    assert item["files_scanned"] == 4 and item["files_imported"] == 2
    assert item["files_skipped"] == 1 and item["completed_at"]
    assert item["errors"] == [{"code": "download_failed"}]
    pending = client.get("/api/v1/sync/jobs?status=pending").json()
    assert pending["total"] == 1 and pending["items"][0]["started_at"] is None
    last = client.get("/api/v1/sync/jobs?page_size=2&page=2").json()
    assert last["items"][0]["id"] == str(UUID(int=1))


@pytest.mark.parametrize("changes", [{"name": " "}, {"status": "invalid"}])
def test_production_constraints(workspace_db, changes):
    _, engine, _ = workspace_db
    with Session(engine) as session:
        session.add(Production(**({"name": "Film"} | changes)))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_production_downgrade(workspace_db):
    _, engine, config = workspace_db
    command.downgrade(config, "0006_asset_imports")
    assert "productions" not in inspect(engine).get_table_names()
    assert "asset_imports" in inspect(engine).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
