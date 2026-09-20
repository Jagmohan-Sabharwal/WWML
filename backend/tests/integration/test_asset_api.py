"""Exercise asset HTTP operations against the migrated PostgreSQL schema."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect, select, update
from sqlalchemy.orm import Session

from alembic import command
from app.api.assets.repository import AssetRepository
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


@pytest.fixture
def api(migrated_database: tuple[Engine, Config]) -> Iterator[TestClient]:
    engine, _ = migrated_database
    application = create_app(Settings(_env_file=None))

    def database_session() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    application.dependency_overrides[get_session] = database_session
    with TestClient(application) as client:
        yield client


def payload(checksum: str = "a" * 64, **overrides: Any) -> dict[str, Any]:
    return {
        "name": "Interview master",
        "description": "Coastal wildlife interview",
        "storage_uri": "gs://wwml-test/interview.mov",
        "media_type": "video",
        "mime_type": "video/quicktime",
        "size_bytes": 1024,
        "sha256": checksum,
    } | overrides


def register(api: TestClient, **overrides: Any) -> dict[str, Any]:
    response = api.post("/assets", json=payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_crud_round_trip(api: TestClient) -> None:
    response = api.post("/assets", json=payload())
    assert response.status_code == 201
    asset = response.json()
    url = f"/assets/{asset['id']}"
    assert response.headers["location"] == url
    assert UUID(asset["id"])
    assert asset["created_at"] and asset["updated_at"]
    assert api.get(url).json() == asset
    updated = api.patch(
        url,
        json={
            "name": "Edited interview",
            "description": None,
            "asset_metadata": {"duration_seconds": 90, "tags": ["reuse"]},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["description"] is None
    assert updated.json()["sha256"] == asset["sha256"]
    assert updated.json()["asset_metadata"]["duration_seconds"] == 90
    assert api.get(url).json() == updated.json()
    deleted = api.delete(url)
    assert deleted.status_code == 204 and deleted.content == b""
    assert api.get(url).status_code == 404
    assert api.get("/assets").json()["total"] == 0


def test_duplicate_returns_reusable_asset_id(api: TestClient) -> None:
    original = register(api)
    duplicate = api.post("/assets", json=payload(storage_uri="gs://wwml-test/copy"))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["existing_asset_id"] == original["id"]
    lookup = api.get("/assets", params={"sha256": original["sha256"]}).json()
    assert [asset["id"] for asset in lookup["items"]] == [original["id"]]


def test_unique_constraint_race_rolls_back(
    api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = register(api)
    find = AssetRepository.find_by_sha256
    calls = 0

    def miss_first(repository: AssetRepository, checksum: str) -> Asset | None:
        nonlocal calls
        calls += 1
        return None if calls == 1 else find(repository, checksum)

    monkeypatch.setattr(AssetRepository, "find_by_sha256", miss_first)
    response = api.post("/assets", json=payload())
    assert response.status_code == 409
    assert response.json()["detail"]["existing_asset_id"] == original["id"]
    assert api.get("/assets").json()["total"] == 1


def test_patch_duplicate_preserves_original_record(api: TestClient) -> None:
    first = register(api)
    second = register(api, checksum="b" * 64)
    response = api.patch(
        f"/assets/{second['id']}", json={"sha256": first["sha256"], "name": "changed"}
    )
    assert response.status_code == 409
    assert api.get(f"/assets/{second['id']}").json() == second


def test_missing_and_malformed_ids(api: TestClient) -> None:
    missing = f"/assets/{uuid4()}"
    assert api.get(missing).status_code == 404
    assert api.patch(missing, json={"name": "missing"}).status_code == 404
    assert api.delete(missing).status_code == 404
    assert api.get("/assets/not-a-uuid").status_code == 422


def test_search_and_filters_combine(api: TestClient) -> None:
    first = register(api)
    register(
        api,
        checksum="b" * 64,
        name="Coastal sound",
        description="Waves",
        media_type="audio",
        mime_type="audio/wav",
    )
    register(api, checksum="c" * 64, name="Mountains", description=None)
    result = api.get("/assets", params={"q": "COASTAL"}).json()
    assert result["total"] == 2
    combined = api.get(
        "/assets",
        params={
            "q": "coastal",
            "media_type": "video",
            "mime_type": "video/quicktime",
        },
    ).json()
    assert [item["id"] for item in combined["items"]] == [first["id"]]
    assert api.get("/assets", params={"q": "' OR 1=1 --"}).json()["total"] == 0


@pytest.mark.parametrize("literal", ["%", "_", "/"])
def test_search_wildcards_are_literal(api: TestClient, literal: str) -> None:
    matched = register(api, name=f"Contains {literal}", description=None)
    register(api, checksum="b" * 64, name="Other", description=None)
    result = api.get("/assets", params={"q": literal}).json()
    assert [item["id"] for item in result["items"]] == [matched["id"]]


def test_pagination_is_bounded_and_deterministic(
    api: TestClient, migrated_database: tuple[Engine, Config]
) -> None:
    engine, _ = migrated_database
    assets = [register(api, checksum=f"{i:064x}") for i in range(5)]
    with engine.begin() as connection:
        connection.execute(
            update(Asset).values(created_at=datetime(2026, 1, 1, tzinfo=UTC))
        )
    pages = [
        api.get("/assets", params={"page": i, "page_size": 2}).json()
        for i in range(1, 4)
    ]
    ids = [item["id"] for page in pages for item in page["items"]]
    assert ids == sorted([asset["id"] for asset in assets], reverse=True)
    assert all(page["total"] == 5 and page["total_pages"] == 3 for page in pages)
    assert len(ids) == len(set(ids)) == 5
    empty = api.get("/assets", params={"page": 4, "page_size": 2}).json()
    assert empty["items"] == [] and empty["total"] == 5
    assert api.get("/assets", params={"page_size": 101}).status_code == 422
    assert api.get("/assets", params={"page": 0}).status_code == 422


def test_empty_results_and_invalid_payloads(api: TestClient) -> None:
    assert api.get("/assets").json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
    }
    assert api.post("/assets", json=payload(size_bytes=-1)).status_code == 422
    asset = register(api)
    assert api.patch(f"/assets/{asset['id']}", json={}).status_code == 422
    assert api.patch(f"/assets/{asset['id']}", json={"name": None}).status_code == 422
    assert api.get("/assets", params={"media_type": "bad"}).status_code == 422


def test_index_migration_preserves_assets(
    migrated_database: tuple[Engine, Config],
) -> None:
    engine, config = migrated_database
    with Session(engine) as session:
        asset = Asset(**payload())
        session.add(asset)
        session.commit()
        asset_id = asset.id
    command.downgrade(config, "0001_create_assets")
    assert "ix_assets_media_type" in {
        i["name"] for i in inspect(engine).get_indexes("assets")
    }
    command.upgrade(config, "head")
    indexes = {i["name"] for i in inspect(engine).get_indexes("assets")}
    assert {
        "ix_assets_created_id",
        "ix_assets_media_created_id",
        "ix_assets_mime_created_id",
    } <= indexes
    with Session(engine) as session:
        assert session.scalar(select(Asset.id)) == asset_id
    command.check(config)
