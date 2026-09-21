"""Versioned PAR behavior against migrated PostgreSQL, including tombstones."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text, update
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.db.session import get_session
from app.main import create_app
from app.models import Asset

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"
    ),
]
API = "/api/v1/assets"


@pytest.fixture
def api(migrated_database) -> Iterator[TestClient]:
    engine, _ = migrated_database
    application = create_app(Settings(_env_file=None))

    def database_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    application.dependency_overrides[get_session] = database_session
    with TestClient(application) as client:
        yield client


def payload(number=1, **overrides):
    return (
        dict(
            name=f"Interview {number}",
            description="Coastal production footage",
            storage_uri=f"s3://wwml/{number}.mp4",
            media_type="video",
            mime_type="video/mp4",
            size_bytes=number * 100,
            sha256=f"{number:064x}",
            asset_metadata={"shot": number},
        )
        | overrides
    )


def register(api, number=1, **overrides):
    response = api.post(API, json=payload(number, **overrides))
    assert response.status_code == 201, response.text
    assert response.headers["location"] == API + "/" + response.json()["id"]
    return response.json()


def test_versioned_crud_retains_deleted_row(api, migrated_database):
    record = register(api)
    url = API + "/" + record["id"]
    assert record["deleted_at"] is None
    assert api.get(url).json() == record
    response = api.patch(url, json={"name": "Selected take", "description": None})
    assert response.status_code == 200
    assert response.json()["description"] is None
    assert api.delete(url).status_code == 204
    assert api.get(url).status_code == 404
    assert api.patch(url, json={"name": "Resurrected"}).status_code == 404
    assert api.delete(url).status_code == 404
    for path in [API, API + "/search", "/assets", "/assets/search"]:
        result = api.get(path, params={"sha256": record["sha256"]}).json()
        assert result["items"] == [] and result["total"] == result["total_pages"] == 0
    engine, _ = migrated_database
    with Session(engine) as session:
        stored = session.get(Asset, UUID(record["id"]))
        assert stored is not None and stored.deleted_at is not None
        assert stored.name == "Selected take"
        assert stored.storage_uri == record["storage_uri"]
        assert stored.asset_metadata == record["asset_metadata"]
        assert stored.updated_at >= stored.created_at


def test_deleted_checksum_stays_canonical_and_reserved(api):
    deleted = register(api)
    other = register(api, 2)
    assert api.delete(API + "/" + deleted["id"]).status_code == 204
    for path in [API, "/assets"]:
        duplicate = api.post(path, json=payload())
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"]["code"] == "asset_deleted"
        assert duplicate.json()["detail"]["existing_asset_id"] == deleted["id"]
    conflict = api.patch(API + "/" + other["id"], json={"sha256": deleted["sha256"]})
    assert conflict.status_code == 409
    assert api.get(API + "/" + other["id"]).json()["sha256"] == other["sha256"]


def test_legacy_delete_also_soft_deletes(api, migrated_database):
    record = register(api)
    assert api.delete("/assets/" + record["id"]).status_code == 204
    engine, _ = migrated_database
    with Session(engine) as session:
        assert session.get(Asset, UUID(record["id"])).deleted_at is not None
    assert api.get(API + "/" + record["id"]).status_code == 404


@pytest.mark.parametrize("sort_by", ["created_at", "updated_at", "name", "size_bytes"])
@pytest.mark.parametrize("direction", ["asc", "desc"])
def test_sorting_pagination_and_ties(api, migrated_database, sort_by, direction):
    records = [register(api, i, name="Same name", size_bytes=100) for i in range(1, 6)]
    engine, _ = migrated_database
    with engine.begin() as connection:
        connection.execute(
            update(Asset).values(
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                updated_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
    deleted_id = records.pop()["id"]
    api.delete(API + "/" + deleted_id)
    pages = [
        api.get(
            API + "/search",
            params={
                "sort_by": sort_by,
                "sort_order": direction,
                "page": page,
                "page_size": 2,
            },
        ).json()
        for page in [1, 2]
    ]
    ids = [item["id"] for page in pages for item in page["items"]]
    assert ids == sorted([item["id"] for item in records], reverse=direction == "desc")
    assert all(page["total"] == 4 and page["total_pages"] == 2 for page in pages)


def test_sorting_uses_requested_column(api, migrated_database):
    first = register(api, 1, name="Zulu")
    second = register(api, 2, name="alpha")
    third = register(api, 3, name="Bravo")
    expected = {
        "name": [second["id"], third["id"], first["id"]],
        "size_bytes": [first["id"], second["id"], third["id"]],
        "created_at": [first["id"], second["id"], third["id"]],
        "updated_at": [first["id"], second["id"], third["id"]],
    }
    engine, _ = migrated_database
    with engine.begin() as connection:
        for index, record in enumerate([first, second, third], start=1):
            stamp = datetime(2026, 1, index, tzinfo=UTC)
            connection.execute(
                update(Asset)
                .where(Asset.id == UUID(record["id"]))
                .values(created_at=stamp, updated_at=stamp)
            )
    for column, ids in expected.items():
        for direction in ["asc", "desc"]:
            response = api.get(
                API + "/search", params={"sort_by": column, "sort_order": direction}
            )
            assert response.status_code == 200
            assert [item["id"] for item in response.json()["items"]] == (
                ids if direction == "asc" else list(reversed(ids))
            )


def test_combined_search_and_inclusive_ranges(api, migrated_database):
    target = register(api, 1, name="50% selected", size_bytes=150)
    register(api, 2, media_type="audio", mime_type="audio/wav", size_bytes=150)
    register(api, 3, size_bytes=300)
    engine, _ = migrated_database
    with engine.begin() as connection:
        connection.execute(
            update(Asset).values(created_at=datetime(2026, 1, 1, tzinfo=UTC))
        )
    query = dict(
        q="%",
        media_type="video",
        mime_type="video/mp4",
        min_size_bytes=150,
        max_size_bytes=150,
        created_after="2026-01-01T01:00:00+01:00",
        created_before="2026-01-01T00:00:00Z",
    )
    response = api.get(API + "/search", params=query)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [target["id"]]
    assert api.get(API, params=query).json() == response.json()
    assert api.get(API + "/search", params={"q": "' OR 1=1 --"}).json()["total"] == 0


@pytest.mark.parametrize(
    "query",
    [
        {"sort_by": "deleted_at"},
        {"sort_order": "invalid"},
        {"min_size_bytes": 10, "max_size_bytes": 1},
        {
            "created_after": "2026-03-01T00:00:00Z",
            "created_before": "2026-01-01T00:00:00Z",
        },
        {"created_after": "2026-01-01T00:00:00"},
        {"include_deleted": "true"},
    ],
)
def test_invalid_search_contract_returns_422(api, query):
    response = api.get(API + "/search", params=query)
    assert response.status_code == 422


def test_migration_upgrades_existing_assets_and_preserves_rows_on_downgrade(
    migrated_database,
):
    engine, config = migrated_database
    command.downgrade(config, "0003_drive_imports")
    asset_id = UUID("10000000-0000-0000-0000-000000000001")
    with engine.begin() as connection:
        connection.execute(
            text("""
            INSERT INTO assets
                (id, name, storage_uri, media_type, mime_type, size_bytes, sha256)
            VALUES (:id, 'Existing footage', 's3://wwml/file',
                    'video', 'video/mp4', 42, :sha)
        """),
            {"id": asset_id, "sha": "f" * 64},
        )
    command.upgrade(config, "head")
    with Session(engine) as session:
        record = session.get(Asset, asset_id)
        assert record is not None and record.deleted_at is None
        record.deleted_at = datetime.now(UTC)
        session.commit()
    assert "ix_assets_active_created_id" in {
        i["name"] for i in inspect(engine).get_indexes("assets")
    }
    command.check(config)
    command.downgrade(config, "0003_drive_imports")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM assets WHERE id = :id"), {"id": asset_id}
            )
            == 1
        )
    command.upgrade(config, "head")
    command.check(config)
