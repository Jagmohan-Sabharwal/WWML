"""Asset lifecycle and exact-file reuse rules."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.api.assets.repository import AssetRepository
from app.api.assets.schemas import (
    AssetCreate,
    AssetPage,
    AssetQuery,
    AssetResponse,
    AssetUpdate,
)
from app.models import Asset


class AssetNotFoundError(Exception):
    """The requested asset record does not exist."""


class DuplicateAssetError(Exception):
    """Identical file bytes are already registered and should be reused."""

    def __init__(self, existing_asset_id: UUID | None) -> None:
        self.existing_asset_id = existing_asset_id
        super().__init__("An asset with this checksum already exists; reuse it.")


class AssetService:
    """Own write transactions while keeping HTTP and persistence separate."""

    def __init__(self, repository: AssetRepository) -> None:
        self.repository = repository

    def get(self, asset_id: UUID) -> Asset:
        asset = self.repository.get(asset_id)
        if asset is None:
            raise AssetNotFoundError
        return asset

    def list(self, query: AssetQuery) -> AssetPage:
        assets, total = self.repository.list(query)
        return AssetPage(
            items=[AssetResponse.model_validate(asset) for asset in assets],
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=(total + query.page_size - 1) // query.page_size,
        )

    def create(self, data: AssetCreate) -> Asset:
        existing = self.repository.find_by_sha256(data.sha256)
        if existing is not None:
            raise DuplicateAssetError(existing.id)
        asset = Asset(**data.model_dump())
        self.repository.add(asset)
        self._commit(data.sha256)
        self.repository.session.refresh(asset)
        return asset

    def update(self, asset_id: UUID, data: AssetUpdate) -> Asset:
        asset = self.get(asset_id)
        if data.sha256 is not None and data.sha256 != asset.sha256:
            existing = self.repository.find_by_sha256(data.sha256)
            if existing is not None:
                raise DuplicateAssetError(existing.id)
        for name, value in data.model_dump(exclude_unset=True).items():
            setattr(asset, name, value)
        checksum = asset.sha256
        self._commit(checksum)
        self.repository.session.refresh(asset)
        return asset

    def delete(self, asset_id: UUID) -> None:
        """Delete registration metadata only; never remove the external media."""
        self.repository.delete(self.get(asset_id))
        self.repository.session.commit()

    def _commit(self, checksum: str) -> None:
        try:
            self.repository.session.commit()
        except IntegrityError as error:
            self.repository.session.rollback()
            diagnostic = getattr(error.orig, "diag", None)
            if getattr(diagnostic, "constraint_name", None) != "uq_assets_sha256":
                raise
            # Handle a competing insert that won after our initial lookup.
            existing = self.repository.find_by_sha256(checksum)
            raise DuplicateAssetError(existing.id if existing else None) from None
