"""Production-scoped, paginated editor review against real PostgreSQL."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("RUN_DB_TESTS") != "1", reason="Requires PostgreSQL"
    ),
]


@pytest.fixture
def editor(migrated_database):
    engine, _ = migrated_database
    app = create_app()

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        yield client


def create(client, path, **data):
    response = client.post("/api/v1" + path, json=data)
    assert response.status_code == 201, response.text
    return response.json()


def plan(client):
    production = create(client, "/productions", name="Video6")
    sequence = create(
        client, f"/productions/{production['id']}/sequences", name="Opening", position=1
    )
    scene = create(
        client,
        f"/sequences/{sequence['id']}/scenes",
        name="Morning Routine",
        position=1,
    )
    shot = create(
        client, f"/scenes/{scene['id']}/shots", name="Luxury Bedroom", position=1
    )
    return production, scene, shot


def test_editor_example_readiness_changes_and_isolation(editor):
    production, scene, shot = plan(editor)
    url = f"/api/v1/productions/{production['id']}/editor"
    page = editor.get(url).json()
    assert page["items"][0]["status"] == "UNPLANNED"
    requirement = create(
        editor,
        f"/shots/{shot['id']}/required-assets",
        name="Bedroom footage",
        position=1,
        media_type="video",
    )
    assert editor.get(url).json()["items"][0]["status"] == "MISSING"
    asset = create(
        editor,
        "/assets",
        name="Bedroom master",
        storage_uri="s3://wwml/bedroom",
        media_type="video",
        mime_type="video/mp4",
        size_bytes=123,
        sha256="a" * 64,
        asset_metadata={"asset_code": "WWML-VID-000045"},
    )
    lock_url = f"/api/v1/required-assets/{requirement['id']}/locked-asset"
    assert editor.put(lock_url, json={"asset_id": asset["id"]}).status_code == 200
    row = editor.get(url).json()["items"][0]
    assert row["scene"]["name"] == "Morning Routine"
    assert row["shot"]["name"] == "Luxury Bedroom"
    assert row["selected_asset"]["reference"] == "WWML-VID-000045"
    assert row["status"] == "READY"
    assert row["locked_asset"]["checksum"] == "a" * 64
    second, _, _ = plan(editor)
    assert editor.get(f"/api/v1/productions/{second['id']}/editor").json()["total"] == 1
    assert editor.get(url).json()["total"] == 1
    editor.patch("/api/v1/assets/" + asset["id"], json={"sha256": "b" * 64})
    review = editor.get(url).json()["items"][0]
    assert review["status"] == "REVIEW"
    assert review["locked_asset"]["checksum"] == "a" * 64
    editor.delete("/api/v1/assets/" + asset["id"])
    assert editor.get(url).json()["items"][0]["status"] == "REVIEW"
    editor.delete(lock_url)
    assert editor.get(url).json()["items"][0]["status"] == "MISSING"
    create(editor, f"/scenes/{scene['id']}/shots", name="Unplanned second", position=2)
    page = editor.get(url + "?page_size=1&page=2").json()
    assert page["total"] == 2 and page["total_pages"] == 2
    assert page["items"][0]["status"] == "UNPLANNED"
    assert editor.get(url + "?page_size=1&page=3").json()["items"] == []


def test_empty_unknown_validation_and_order(editor):
    production = create(editor, "/productions", name="Empty")
    url = f"/api/v1/productions/{production['id']}/editor"
    assert editor.get(url).json()["items"] == []
    assert editor.get(url).json()["total_pages"] == 0
    assert editor.get(f"/api/v1/productions/{uuid4()}/editor").status_code == 404
    for query in ("page=0", "page_size=101", "unknown=yes"):
        assert editor.get(url + "?" + query).status_code == 422
    for position in (2, 1):
        sequence = create(
            editor,
            f"/productions/{production['id']}/sequences",
            name=f"Sequence {position}",
            position=position,
        )
        scene = create(
            editor, f"/sequences/{sequence['id']}/scenes", name="Scene", position=1
        )
        shot = create(editor, f"/scenes/{scene['id']}/shots", name="Shot", position=1)
        for index in (2, 1):
            create(
                editor,
                f"/shots/{shot['id']}/required-assets",
                name=f"Need {index}",
                position=index,
                media_type="video",
            )
    rows = editor.get(url).json()["items"]
    assert [
        (row["sequence"]["position"], row["requirement"]["position"]) for row in rows
    ] == [(1, 1), (1, 2), (2, 1), (2, 2)]
