"""Readiness is based on selection facts, never a hardcoded production label."""

from datetime import UTC, datetime

import pytest

from app.api.editor.service import asset_reference, readiness
from app.models import Asset
from app.models.production_structure import LockedAsset, RequiredAsset


@pytest.mark.parametrize(
    "case,expected",
    [
        ("ready", "READY"),
        ("unplanned", "UNPLANNED"),
        ("missing", "MISSING"),
        ("deleted", "REVIEW"),
        ("changed_hash", "REVIEW"),
        ("changed_uri", "REVIEW"),
        ("changed_type", "REVIEW"),
        ("missing_asset", "REVIEW"),
    ],
)
def test_readiness(case, expected):
    requirement = RequiredAsset(media_type="video")
    lock = LockedAsset(checksum="a" * 64, storage_uri="s3://wwml/a")
    asset = Asset(
        sha256="a" * 64, storage_uri="s3://wwml/a", media_type="video", deleted_at=None
    )
    if case == "unplanned":
        requirement = None
    if case == "missing":
        lock = None
    if case == "deleted":
        asset.deleted_at = datetime.now(UTC)
    if case == "changed_hash":
        asset.sha256 = "b" * 64
    if case == "changed_uri":
        asset.storage_uri = "s3://wwml/b"
    if case == "changed_type":
        asset.media_type = "audio"
    if case == "missing_asset":
        asset = None
    status, reason = readiness(requirement, lock, asset)
    assert status == expected and reason


@pytest.mark.parametrize(
    "value,expected",
    [
        ("WWML-VID-000045", "WWML-VID-000045"),
        (None, "Source"),
        ("", "Source"),
        ({"bad": "value"}, "Source"),
        ("<script>", "Source"),
    ],
)
def test_display_reference_is_optional_and_validated(value, expected):
    assert (
        asset_reference(Asset(name="Source", asset_metadata={"asset_code": value}))
        == expected
    )
