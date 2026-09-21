"""SQLAlchemy persistence operations; transaction ownership stays in the service."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.api.assets.schemas import AssetQuery
from app.models import Asset


class AssetRepository:
    """Store and discover reusable assets without triggering media generation."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, asset_id: UUID, *, for_update: bool = False) -> Asset | None:
        statement = select(Asset).where(
            Asset.id == asset_id, Asset.deleted_at.is_(None)
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def find_by_sha256(self, checksum: str) -> Asset | None:
        """Include tombstones so the canonical checksum is never registered twice."""
        return self.session.scalar(select(Asset).where(Asset.sha256 == checksum))

    def add(self, asset: Asset) -> None:
        self.session.add(asset)

    def delete(self, asset: Asset) -> None:
        # Preserve the row, references and source bytes; only mark its lifecycle.
        asset.deleted_at = datetime.now(UTC)

    def list(self, query: AssetQuery) -> tuple[list[Asset], int]:
        """Use bound parameters and escaped LIKE patterns for literal search."""
        predicates: list[ColumnElement[bool]] = [Asset.deleted_at.is_(None)]
        if query.q is not None:
            predicates.append(
                or_(
                    Asset.name.icontains(query.q, autoescape=True),
                    Asset.description.icontains(query.q, autoescape=True),
                )
            )
        if query.media_type is not None:
            predicates.append(Asset.media_type == query.media_type)
        if query.mime_type is not None:
            predicates.append(Asset.mime_type == query.mime_type)
        if query.sha256 is not None:
            predicates.append(Asset.sha256 == query.sha256)
        if query.min_size_bytes is not None:
            predicates.append(Asset.size_bytes >= query.min_size_bytes)
        if query.max_size_bytes is not None:
            predicates.append(Asset.size_bytes <= query.max_size_bytes)
        if query.created_after is not None:
            predicates.append(Asset.created_at >= query.created_after)
        if query.created_before is not None:
            predicates.append(Asset.created_at <= query.created_before)
        column = {
            "created_at": Asset.created_at,
            "updated_at": Asset.updated_at,
            "name": func.lower(Asset.name),
            "size_bytes": Asset.size_bytes,
        }[query.sort_by]
        ordering = (
            (column.asc(), Asset.id.asc())
            if query.sort_order == "asc"
            else (column.desc(), Asset.id.desc())
        )
        total = self.session.scalar(
            select(func.count()).select_from(Asset).where(*predicates)
        )
        rows = self.session.scalars(
            select(Asset)
            .where(*predicates)
            .order_by(*ordering)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        return list(rows), int(total or 0)
