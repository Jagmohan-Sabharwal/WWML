"""PAR contracts and isolated service/repository behavior without PostgreSQL."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError

from app.api.assets.repository import AssetRepository
from app.api.assets.router import get_asset_service
from app.api.assets.schemas import AssetCreate, AssetPage, AssetQuery, AssetUpdate
from app.api.assets.service import AssetNotFoundError, AssetService, DuplicateAssetError
from app.models import Asset


def asset(**changes):
    values = dict(
        id=uuid4(),
        name="Interview",
        description=None,
        storage_uri="s3://wwml/interview.mp4",
        media_type="video",
        mime_type="video/mp4",
        size_bytes=1024,
        sha256="a" * 64,
        asset_metadata={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
    )
    return Asset(**(values | changes))


@pytest.mark.parametrize(
    "values",
    [
        {"sort_by": "storage_uri; DROP TABLE assets"},
        {"sort_order": "sideways"},
        {"min_size_bytes": -1},
        {"max_size_bytes": 2**63},
        {"min_size_bytes": 100, "max_size_bytes": 99},
        {"created_after": "2026-01-01T00:00:00"},
        {
            "created_after": "2026-02-01T00:00:00Z",
            "created_before": "2026-01-01T00:00:00Z",
        },
    ],
)
def test_query_rejects_invalid_sort_and_ranges(values):
    with pytest.raises(ValidationError):
        AssetQuery.model_validate(values)


def test_query_accepts_inclusive_ranges_and_timezones():
    query = AssetQuery(
        min_size_bytes=0,
        max_size_bytes=0,
        created_after="2026-01-01T01:00:00+01:00",
        created_before="2026-01-01T00:00:00Z",
    )
    assert query.created_after == query.created_before


@pytest.mark.parametrize(
    "schema, payload",
    [
        (AssetCreate, {"deleted_at": "2026-01-01T00:00:00Z"}),
        (AssetUpdate, {"deleted_at": None}),
    ],
)
def test_tombstones_cannot_be_written_or_restored_by_payload(schema, payload):
    with pytest.raises(ValidationError):
        schema.model_validate(payload)


def test_repository_filters_reads_and_locks_mutations():
    session = MagicMock()
    repository = AssetRepository(session)
    repository.get(uuid4(), for_update=True)
    sql = str(session.scalar.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "assets.deleted_at IS NULL" in sql
    assert "FOR UPDATE" in sql
    session.get.assert_not_called()


def test_repository_soft_delete_never_emits_hard_delete():
    session = MagicMock()
    repository = AssetRepository(session)
    record = asset()
    repository.delete(record)
    assert record.deleted_at is not None and record.deleted_at.tzinfo is not None
    session.delete.assert_not_called()
    session.commit.assert_not_called()


def test_repository_binds_literal_search_and_applies_sort_to_rows():
    session = MagicMock()
    session.scalar.return_value = 1
    session.scalars.return_value.all.return_value = [asset()]
    repository = AssetRepository(session)
    query = AssetQuery(
        q="50%_' OR 1=1", sort_by="name", sort_order="asc", page=2, page_size=3
    )
    items, total = repository.list(query)
    statement = session.scalars.call_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(statement)
    assert "ORDER BY lower(assets.name) ASC, assets.id ASC" in sql
    assert "assets.deleted_at IS NULL" in sql
    assert query.q not in sql
    assert statement.params["param_1"] == 3  # LIMIT
    assert statement.params["param_2"] == 3  # OFFSET
    assert total == 1 and len(items) == 1
    count_sql = str(session.scalar.call_args.args[0])
    assert "assets.deleted_at IS NULL" in count_sql


def test_service_commits_soft_delete_and_locks_record():
    repository = MagicMock(spec=AssetRepository)
    repository.session = MagicMock()
    record = asset()
    repository.get.return_value = record
    service = AssetService(repository)
    service.delete(record.id)
    repository.get.assert_called_once_with(record.id, for_update=True)
    repository.delete.assert_called_once_with(record)
    repository.session.commit.assert_called_once()
    repository.session.delete.assert_not_called()


def test_service_missing_asset_never_commits():
    repository = MagicMock(spec=AssetRepository)
    repository.session = MagicMock()
    repository.get.return_value = None
    with pytest.raises(AssetNotFoundError):
        AssetService(repository).delete(uuid4())
    repository.session.commit.assert_not_called()


def test_service_update_retains_omitted_fields():
    repository = MagicMock(spec=AssetRepository)
    repository.session = MagicMock()
    record = asset(description="Original")
    repository.get.return_value = record
    result = AssetService(repository).update(record.id, AssetUpdate(name="Renamed"))
    assert result.name == "Renamed" and result.description == "Original"
    repository.get.assert_called_once_with(record.id, for_update=True)
    repository.session.commit.assert_called_once()


def test_service_create_rejects_tombstone_checksum():
    repository = MagicMock(spec=AssetRepository)
    repository.session = MagicMock()
    original = asset(deleted_at=datetime.now(UTC))
    repository.find_by_sha256.return_value = original
    data = AssetCreate(
        name="Duplicate",
        storage_uri="s3://wwml/copy",
        media_type="video",
        mime_type="video/mp4",
        size_bytes=1024,
        sha256=original.sha256,
    )
    with pytest.raises(DuplicateAssetError) as caught:
        AssetService(repository).create(data)
    assert caught.value.deleted and caught.value.existing_asset_id == original.id
    repository.add.assert_not_called()


def test_service_race_rolls_back_and_reports_tombstone():
    repository = MagicMock(spec=AssetRepository)
    repository.session = MagicMock()
    original = asset(deleted_at=datetime.now(UTC))
    repository.find_by_sha256.return_value = original
    error = Exception("database diagnostic")
    error.diag = SimpleNamespace(constraint_name="uq_assets_sha256")
    repository.session.commit.side_effect = IntegrityError("statement", {}, error)
    with pytest.raises(DuplicateAssetError) as caught:
        AssetService(repository)._commit(original.sha256)
    assert caught.value.deleted
    repository.session.rollback.assert_called_once()


def test_other_database_errors_are_not_misreported_as_duplicates():
    repository = MagicMock(spec=AssetRepository)
    repository.session = MagicMock()
    repository.session.commit.side_effect = IntegrityError("statement", {}, Exception())
    with pytest.raises(IntegrityError):
        AssetService(repository)._commit("a" * 64)
    repository.session.rollback.assert_called_once()
    repository.find_by_sha256.assert_not_called()


def test_versioned_search_precedes_uuid_route_and_is_documented(application):
    service = MagicMock(spec=AssetService)
    service.list.return_value = AssetPage(
        items=[], total=0, page=1, page_size=20, total_pages=0
    )
    application.dependency_overrides[get_asset_service] = lambda: service
    with TestClient(application) as client:
        assert (
            client.get("/api/v1/assets/search", params={"sort_by": "name"}).status_code
            == 200
        )
        assert client.get("/api/v1/assets/not-an-id").status_code == 422
    paths = application.openapi()["paths"]
    for path in [
        "/api/v1/assets",
        "/api/v1/assets/search",
        "/api/v1/assets/{asset_id}",
    ]:
        assert path in paths
    parameters = {
        p["name"] for p in paths["/api/v1/assets/search"]["get"]["parameters"]
    }
    assert {
        "sort_by",
        "sort_order",
        "created_after",
        "created_before",
        "min_size_bytes",
        "max_size_bytes",
        "media_type",
        "mime_type",
        "sha256",
        "q",
        "page",
        "page_size",
    } == parameters
    assert paths["/assets"]["get"]["deprecated"] is True
    assert not paths["/api/v1/assets"]["get"].get("deprecated", False)
