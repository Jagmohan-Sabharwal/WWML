"""Planning invariants and explicit asset-lock transactions."""

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import InstrumentedAttribute

from app.api.production_structure.repository import PlanningRepository
from app.api.production_structure.schemas import LockResponse
from app.api.workspace.schemas import Page, PageQuery
from app.db.base import Base
from app.models import Asset
from app.models.production_structure import LockedAsset, OrderedNode, RequiredAsset


class PlanningError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        super().__init__(message)


class PlanningService:
    def __init__(self, repository: PlanningRepository) -> None:
        self.repository = repository

    def require[T: Base](
        self, model: type[T], identifier: UUID, *, lock: bool = False
    ) -> T:
        row = self.repository.get(model, identifier, lock=lock)
        if row is None:
            raise PlanningError(404, "record_not_found", "Planning record not found.")
        return row

    def create[T: Base](self, row: T) -> T:
        self.repository.add(row)
        self.commit()
        self.repository.session.refresh(row)
        return row

    def children[T: OrderedNode, R: BaseModel](
        self,
        model: type[T],
        parent_column: InstrumentedAttribute[UUID],
        parent_id: UUID,
        query: PageQuery,
        response: type[R],
    ) -> Page[R]:
        rows, total = self.repository.children(model, parent_column, parent_id, query)
        return Page(
            items=[response.model_validate(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=(total + query.page_size - 1) // query.page_size,
        )

    def lock(self, requirement_id: UUID, asset_id: UUID) -> LockResponse:
        # All lock/unlock requests serialize on the requirement, even if no lock exists.
        requirement = self.require(RequiredAsset, requirement_id, lock=True)
        existing = self.repository.get(LockedAsset, requirement_id)
        if existing is not None:
            if existing.asset_id != asset_id:
                raise PlanningError(
                    409,
                    "already_locked",
                    "Unlock the current selection before replacing it.",
                )
            snapshot = LockResponse.model_validate(existing)
            self.commit()
            return snapshot
        asset = self.repository.get(Asset, asset_id, lock=True)
        if asset is None or asset.deleted_at is not None:
            raise PlanningError(
                404, "asset_not_found", "Active registry asset not found."
            )
        if asset.media_type != requirement.media_type:
            raise PlanningError(
                409,
                "media_type_mismatch",
                "Asset media type does not match the requirement.",
            )
        selection = LockedAsset(
            required_asset_id=requirement_id,
            asset_id=asset_id,
            checksum=asset.sha256,
            storage_uri=asset.storage_uri,
        )
        self.repository.add(selection)
        # Capture server defaults while row locks are held. A subsequent unlock
        # must not expire the response or cause a post-commit refresh to fail.
        self.repository.session.flush()
        snapshot = LockResponse.model_validate(selection)
        self.commit()
        return snapshot

    def unlock(self, requirement_id: UUID) -> None:
        self.require(RequiredAsset, requirement_id, lock=True)
        existing = self.repository.get(LockedAsset, requirement_id)
        if existing is not None:
            self.repository.remove_lock(existing)
        self.commit()

    def commit(self) -> None:
        try:
            self.repository.session.commit()
        except IntegrityError as error:
            self.repository.session.rollback()
            code = getattr(error.orig, "sqlstate", None)
            if code == "23505":
                raise PlanningError(
                    409,
                    "position_conflict",
                    "This sibling position is already occupied.",
                ) from None
            if code == "23503":
                raise PlanningError(
                    409, "parent_changed", "The referenced record no longer exists."
                ) from None
            raise
