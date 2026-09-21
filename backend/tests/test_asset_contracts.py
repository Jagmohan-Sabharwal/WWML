"""Validate client contracts and Swagger without a database."""

from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api.assets.schemas import AssetCreate, AssetQuery, AssetUpdate


def asset_payload(**overrides: Any) -> dict[str, Any]:
    return {
        "name": "Interview",
        "storage_uri": "gs://wwml/interview.mp4",
        "media_type": "video",
        "mime_type": "video/mp4",
        "size_bytes": 1024,
        "sha256": "a" * 64,
    } | overrides


@pytest.mark.parametrize(
    "changes",
    [
        {"name": " "},
        {"storage_uri": ""},
        {"media_type": "invalid"},
        {"mime_type": "invalid"},
        {"size_bytes": -1},
        {"size_bytes": 2**63},
        {"size_bytes": True},
        {"sha256": "A" * 64},
        {"sha256": "not-a-hash"},
        {"unknown": True},
        {"asset_metadata": None},
    ],
)
def test_create_rejects_invalid_fields(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AssetCreate.model_validate(asset_payload(**changes))


@pytest.mark.parametrize(
    "changes", [{}, {"name": None}, {"asset_metadata": None}, {"id": "new"}]
)
def test_patch_rejects_empty_null_and_readonly_fields(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AssetUpdate.model_validate(changes)


def test_patch_distinguishes_omitted_description_from_explicit_null() -> None:
    assert AssetUpdate(name="New").model_dump(exclude_unset=True) == {"name": "New"}
    assert AssetUpdate(description=None).model_dump(exclude_unset=True) == {
        "description": None
    }


@pytest.mark.parametrize(
    "query",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
        {"q": " "},
        {"q": "x" * 201},
        {"page": 1000001},
    ],
)
def test_list_bounds(query: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AssetQuery.model_validate(query)


def test_swagger_documents_crud_filters_and_errors(application: FastAPI) -> None:
    paths = application.openapi()["paths"]
    assert set(paths["/assets"]) == {"get", "post"}
    assert set(paths["/assets/{asset_id}"]) == {"get", "patch", "delete"}
    assert "201" in paths["/assets"]["post"]["responses"]
    assert "409" in paths["/assets"]["post"]["responses"]
    assert "404" in paths["/assets/{asset_id}"]["get"]["responses"]
    assert "204" in paths["/assets/{asset_id}"]["delete"]["responses"]
    assert "422" in paths["/assets"]["get"]["responses"]
    parameters = {p["name"] for p in paths["/assets"]["get"]["parameters"]}
    assert {"q", "page", "page_size", "media_type", "mime_type", "sha256"} <= parameters
