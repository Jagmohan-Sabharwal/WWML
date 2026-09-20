"""SQLAlchemy persistence operations; transaction ownership stays in the service."""

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

    def get(self, asset_id: UUID) -> Asset | None:
        return self.session.get(Asset, asset_id)

    def find_by_sha256(self, checksum: str) -> Asset | None:
        return self.session.scalar(select(Asset).where(Asset.sha256 == checksum))

    def add(self, asset: Asset) -> None:
        self.session.add(asset)

    def delete(self, asset: Asset) -> None:
        self.session.delete(asset)

    def list(self, query: AssetQuery) -> tuple[list[Asset], int]:
        """Use bound parameters and escaped LIKE patterns for literal search."""
        predicates: list[ColumnElement[bool]] = []
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
        total = self.session.scalar(
            select(func.count()).select_from(Asset).where(*predicates)
        )
        rows = self.session.scalars(
            select(Asset)
            .where(*predicates)
            .order_by(Asset.created_at.desc(), Asset.id.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        return list(rows), int(total or 0)
