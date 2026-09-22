"""Real PostgreSQL planning, selection, isolation and migration guarantees."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.db.session import get_session
from app.main import create_app
from app.models import Asset, Production
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


@pytest.fixture
def planning(migrated_database):
    engine, config = migrated_database
    app = create_app()

    def sessions():
        with Session(engine) as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        yield client, engine, config


def post(client, path, **body):
    response = client.post("/api/v1" + path, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def hierarchy(client):
    production = post(client, "/productions", name="Documentary")
    sequence_path = f"/productions/{production['id']}/sequences"
    sequence = post(client, sequence_path, name="Opening", position=1)
    scene_path = f"/sequences/{sequence['id']}/scenes"
    scene = post(client, scene_path, name="Interview", position=1)
    shot_path = f"/scenes/{scene['id']}/shots"
    shot = post(client, shot_path, name="Closeup", position=1)
    requirement_path = f"/shots/{shot['id']}/required-assets"
    requirement = post(
        client,
        requirement_path,
        name="Interview footage",
        position=1,
        media_type="video",
    )
    return (
        production,
        [sequence_path, scene_path, shot_path, requirement_path],
        requirement,
    )


def asset(client, checksum="a", media="video"):
    return post(
        client,
        "/assets",
        name="Existing footage",
        storage_uri=f"s3://wwml/{checksum}",
        media_type=media,
        mime_type="video/mp4" if media == "video" else "audio/mpeg",
        size_bytes=123,
        sha256=checksum * 64,
    )


def lock_url(requirement):
    return f"/api/v1/required-assets/{requirement['id']}/locked-asset"


def test_end_to_end_creation_traversal_and_pagination(planning):
    client, _, config = planning
    production, paths, requirement = hierarchy(client)
    assert (
        client.get(f"/api/v1/productions/{production['id']}").json()["name"]
        == "Documentary"
    )
    for path in paths:
        page = client.get("/api/v1" + path).json()
        assert page["total"] == 1 and page["items"][0]["position"] == 1
        assert (
            client.get("/api/v1" + path + "?page=2&page_size=1").json()["items"] == []
        )
        conflict = client.post(
            "/api/v1" + path,
            json={
                "name": "Duplicate position",
                "position": 1,
                **({"media_type": "video"} if path.endswith("required-assets") else {}),
            },
        )
        assert conflict.status_code == 409
    for position in (3, 2):
        post(client, paths[0], name=f"Sequence {position}", position=position)
    page = client.get("/api/v1" + paths[0] + "?page_size=2").json()
    assert [row["position"] for row in page["items"]] == [1, 2]
    assert page["total"] == 3
    other, other_paths, _ = hierarchy(client)
    assert other["id"] != production["id"]
    assert client.get("/api/v1" + other_paths[0]).json()["total"] == 1
    existing = asset(client)
    locked = client.put(lock_url(requirement), json={"asset_id": existing["id"]})
    assert locked.status_code == 200
    assert locked.json()["checksum"] == "a" * 64
    assert locked.json()["storage_uri"] == existing["storage_uri"]
    assert locked.json()["locked_at"]
    command.check(config)


def test_lock_reuse_retry_snapshot_and_unlock(planning):
    client, engine, _ = planning
    _, paths, requirement = hierarchy(client)
    first, second = asset(client), asset(client, "b")
    url = lock_url(requirement)
    assert client.get(url).status_code == 404
    locked = client.put(url, json={"asset_id": first["id"]}).json()
    assert client.put(url, json={"asset_id": first["id"]}).json() == locked
    assert client.put(url, json={"asset_id": second["id"]}).status_code == 409
    another = post(
        client, paths[-1], name="Reusable footage", position=2, media_type="video"
    )
    assert (
        client.put(lock_url(another), json={"asset_id": first["id"]}).status_code == 200
    )
    assert (
        client.patch(
            "/api/v1/assets/" + first["id"],
            json={"sha256": "c" * 64, "storage_uri": "s3://wwml/changed"},
        ).status_code
        == 200
    )
    assert client.delete("/api/v1/assets/" + first["id"]).status_code == 204
    assert client.get(url).json() == locked
    assert client.put(url, json={"asset_id": first["id"]}).json() == locked
    assert client.delete(url).status_code == 204
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert client.put(url, json={"asset_id": first["id"]}).status_code == 404
    assert client.put(url, json={"asset_id": second["id"]}).status_code == 200
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 2
        assert session.scalar(select(func.count()).select_from(RequiredAsset)) == 2


def test_missing_parents_validation_and_media_mismatch(planning):
    client, _, _ = planning
    for path in (
        f"/productions/{uuid4()}/sequences",
        f"/sequences/{uuid4()}/scenes",
        f"/scenes/{uuid4()}/shots",
        f"/shots/{uuid4()}/required-assets",
    ):
        assert client.get("/api/v1" + path).status_code == 404
        data = {"name": "Child", "position": 1}
        if path.endswith("required-assets"):
            data["media_type"] = "video"
        assert client.post("/api/v1" + path, json=data).status_code == 404
    _, paths, requirement = hierarchy(client)
    assert client.get("/api/v1" + paths[0] + "?page_size=101").status_code == 422
    assert (
        client.post("/api/v1" + paths[0], json={"name": " ", "position": 1}).status_code
        == 422
    )
    assert (
        client.put(lock_url(requirement), json={"asset_id": str(uuid4())}).status_code
        == 404
    )
    audio = asset(client, media="audio")
    response = client.put(lock_url(requirement), json={"asset_id": audio["id"]})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "media_type_mismatch"


def test_competing_locks_keep_one_choice(planning):
    client, engine, _ = planning
    _, _, requirement = hierarchy(client)
    assets = [asset(client), asset(client, "b")]
    barrier = Barrier(2)

    def choose(row):
        barrier.wait(timeout=10)
        return client.put(lock_url(requirement), json={"asset_id": row["id"]})

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(choose, assets))
    assert sorted(response.status_code for response in results) == [200, 409]
    winner = next(
        response.json() for response in results if response.status_code == 200
    )
    assert client.get(lock_url(requirement)).json() == winner
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(LockedAsset)) == 1


def test_foreign_keys_and_parent_retention(planning):
    client, engine, _ = planning
    production, _, requirement = hierarchy(client)
    existing = asset(client)
    client.put(lock_url(requirement), json={"asset_id": existing["id"]})
    with Session(engine) as session:
        from uuid import UUID

        for model, identifier in (
            (Production, production["id"]),
            (Asset, existing["id"]),
            (RequiredAsset, requirement["id"]),
        ):
            row = session.get(model, UUID(identifier))
            session.delete(row)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
        for model, parent in (
            (ProductionSequence, "production_id"),
            (Scene, "sequence_id"),
            (Shot, "scene_id"),
            (RequiredAsset, "shot_id"),
        ):
            row = model(
                name="Orphan",
                position=1,
                **{parent: uuid4()},
                **({"media_type": "video"} if model is RequiredAsset else {}),
            )
            session.add(row)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()


def test_migration_roundtrip_preserves_production_and_registry(planning):
    client, engine, config = planning
    hierarchy(client)
    asset(client)
    command.downgrade(config, "0007_productions")
    assert "shots" not in inspect(engine).get_table_names()
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Production)) == 1
        assert session.scalar(select(func.count()).select_from(Asset)) == 1
    command.upgrade(config, "head")
    command.check(config)
