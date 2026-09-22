"""Dashboard aggregation uses full production scope and separates global activity."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.main import create_app
from app.models import Asset, DriveImport, Production, SyncJob
from app.models.production_structure import (
    LockedAsset,
    ProductionSequence,
    RequiredAsset,
    Scene,
    Shot,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"
    ),
]


def test_dashboard_counts_and_shared_scope(migrated_database):
    engine, _ = migrated_database
    now = datetime.now(UTC)
    with Session(engine) as session:
        production = Production(name="Video #6")
        session.add(production)
        session.flush()
        sequence = ProductionSequence(
            production_id=production.id, name="Opening", position=1
        )
        session.add(sequence)
        session.flush()
        scene = Scene(sequence_id=sequence.id, name="Morning Routine", position=1)
        session.add(scene)
        session.flush()
        shots = [
            Shot(scene_id=scene.id, name=f"Shot {i}", position=i) for i in range(1, 5)
        ]
        session.add_all(shots)
        session.flush()
        requirements = [
            RequiredAsset(
                shot_id=shot.id, name="Footage", position=1, media_type="video"
            )
            for shot in shots[:3]
        ]
        session.add_all(requirements)
        session.flush()
        asset = Asset(
            name="Bedroom",
            storage_uri="s3://wwml/a",
            media_type="video",
            mime_type="video/mp4",
            size_bytes=1,
            sha256="a" * 64,
        )
        session.add(asset)
        session.flush()
        session.add_all(
            [
                LockedAsset(
                    required_asset_id=requirements[0].id,
                    asset_id=asset.id,
                    checksum=asset.sha256,
                    storage_uri=asset.storage_uri,
                ),
                LockedAsset(
                    required_asset_id=requirements[1].id,
                    asset_id=asset.id,
                    checksum="b" * 64,
                    storage_uri=asset.storage_uri,
                ),
                SyncJob(status="running", started_at=now),
                DriveImport(
                    file_id="queued",
                    source_version="1",
                    source_name="Queued.mov",
                    status="watch",
                ),
                DriveImport(
                    file_id="failed",
                    source_version="1",
                    source_name="Failed.mov",
                    status="failed",
                ),
                DriveImport(
                    file_id="done",
                    source_version="1",
                    source_name="Latest.mov",
                    status="done",
                ),
                Production(name="Empty"),
            ]
        )
        session.commit()
        identifier = str(production.id)
    app = create_app()

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        response = client.get(f"/api/v1/productions/{identifier}/dashboard")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["production"]["name"] == "Video #6"
        assert data["assets_ready"] == 1 and data["missing_assets"] == 1
        assert data["assets_to_review"] == 1 and data["unplanned_shots"] == 1
        assert data["required_assets"] == 3 and data["progress_percent"] == 25
        assert data["ai_gaps"] is None and data["credits_saved"] is None
        assert data["activity_scope"] == "shared_library"
        assert data["import_queue"] == 1 and data["failed_imports"] == 1
        assert data["latest_sync_job"]["status"] == "running"
        assert [item["source_name"] for item in data["latest_imports"]] == [
            "Latest.mov"
        ]
        rows = client.get(f"/api/v1/productions/{identifier}/editor").json()["items"]
        assert sum(row["status"] == "READY" for row in rows) == data["assets_ready"]
        empty = next(
            item
            for item in client.get("/api/v1/productions").json()["items"]
            if item["name"] == "Empty"
        )
        empty_data = client.get(f"/api/v1/productions/{empty['id']}/dashboard").json()
        assert empty_data["progress_percent"] is None
        assert empty_data["required_assets"] == 0
        assert empty_data["import_queue"] == 1
        assert client.get(f"/api/v1/productions/{uuid4()}/dashboard").status_code == 404


def test_empty_shared_activity_and_latest_limit(migrated_database):
    engine, _ = migrated_database
    with Session(engine) as session:
        production = Production(name="Empty")
        session.add(production)
        session.commit()
        identifier = str(production.id)
    app = create_app()

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        data = client.get(f"/api/v1/productions/{identifier}/dashboard").json()
        assert data["latest_sync_job"] is None and data["latest_imports"] == []
        assert data["import_queue"] == 0
        with Session(engine) as session:
            session.add_all(
                [
                    DriveImport(
                        file_id=f"file{i}",
                        source_version="1",
                        source_name=f"{i}.mov",
                        status="done",
                        updated_at=datetime(2026, 1, i + 1, tzinfo=UTC),
                    )
                    for i in range(7)
                ]
            )
            session.commit()
        data = client.get(f"/api/v1/productions/{identifier}/dashboard").json()
        assert [item["source_name"] for item in data["latest_imports"]] == [
            "6.mov",
            "5.mov",
            "4.mov",
            "3.mov",
            "2.mov",
        ]
