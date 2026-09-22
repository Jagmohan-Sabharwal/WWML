"""Planning input validation, lock invariants and OpenAPI contracts."""

from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.production_structure.repository import PlanningRepository
from app.api.production_structure.schemas import NodeCreate, RequirementCreate
from app.api.production_structure.service import PlanningError, PlanningService
from app.main import create_app
from app.models import Asset
from app.models.production_structure import LockedAsset, RequiredAsset


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "  "},
        {"position": 0},
        {"position": -1},
        {"position": True},
        {"position": 1.5},
        {"position": 2147483648},
        {"extra": "value"},
    ],
)
def test_node_validation(changes):
    with pytest.raises(ValidationError):
        NodeCreate(**({"name": "Scene", "position": 1} | changes))


def test_requirement_validates_media_and_strips_name():
    data = RequirementCreate(name="  Interview  ", position=1, media_type="video")
    assert data.name == "Interview"
    with pytest.raises(ValidationError):
        RequirementCreate(name="Interview", position=1, media_type="anything")


@pytest.mark.parametrize(
    "deleted,mismatch,expected",
    [
        (True, False, "asset_not_found"),
        (False, True, "media_type_mismatch"),
    ],
)
def test_lock_rejects_unusable_asset(deleted, mismatch, expected):
    repository = Mock(spec=PlanningRepository)
    repository.session = Mock()
    requirement_id, asset_id = uuid4(), uuid4()
    requirement = RequiredAsset(id=requirement_id, media_type="video")
    asset = Asset(id=asset_id, media_type="audio" if mismatch else "video")
    asset.deleted_at = Mock() if deleted else None
    repository.get.side_effect = [requirement, None, asset]
    with pytest.raises(PlanningError) as error:
        PlanningService(repository).lock(requirement_id, asset_id)
    assert error.value.code == expected
    repository.add.assert_not_called()
    repository.session.commit.assert_not_called()
    assert repository.get.call_args_list[0].kwargs == {"lock": True}
    assert repository.get.call_args_list[-1].kwargs == {"lock": True}


def test_lock_preserves_existing_snapshot_on_idempotent_retry():
    repository = Mock(spec=PlanningRepository)
    repository.session = Mock()
    requirement_id, asset_id = uuid4(), uuid4()
    existing = LockedAsset(
        required_asset_id=requirement_id,
        asset_id=asset_id,
        checksum="a" * 64,
        storage_uri="s3://wwml/a",
        locked_at=datetime.now(UTC),
    )
    repository.get.side_effect = [RequiredAsset(id=requirement_id), existing]
    snapshot = PlanningService(repository).lock(requirement_id, asset_id)
    assert snapshot.asset_id == asset_id
    assert snapshot.checksum == existing.checksum
    assert snapshot.locked_at == existing.locked_at
    assert repository.get.call_count == 2
    repository.add.assert_not_called()


def test_lock_requires_explicit_unlock_to_replace():
    repository = Mock(spec=PlanningRepository)
    repository.get.side_effect = [RequiredAsset(), LockedAsset(asset_id=uuid4())]
    with pytest.raises(PlanningError) as error:
        PlanningService(repository).lock(uuid4(), uuid4())
    assert error.value.status == 409
    assert error.value.code == "already_locked"


def test_documented_paths_and_schemas():
    with TestClient(create_app()) as client:
        paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/productions",
        "/productions/{production_id}/sequences",
        "/sequences/{sequence_id}/scenes",
        "/scenes/{scene_id}/shots",
        "/shots/{shot_id}/required-assets",
    ):
        assert {"post", "get"} <= paths[f"/api/v1{path}"].keys()
    lock = paths["/api/v1/required-assets/{requirement_id}/locked-asset"]
    assert {"put", "get", "delete"} <= lock.keys()
    assert lock["put"]["responses"]["409"]["content"]["application/json"]["schema"]
