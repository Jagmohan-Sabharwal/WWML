"""Database reads; aggregate in SQL rather than loading full registries."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.workspace.schemas import ProductionQuery, SyncQuery
from app.models import Asset, SyncJob
from app.models.production import Production


class WorkspaceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def asset_groups(self) -> list[tuple[str, int, int]]:
        rows = self.session.execute(
            select(Asset.media_type, func.count(), func.sum(Asset.size_bytes))
            .where(Asset.deleted_at.is_(None))
            .group_by(Asset.media_type)
        )
        return [(kind, int(count), int(size)) for kind, count, size in rows]

    def production_counts(self) -> dict[str, int]:
        return dict(
            self.session.execute(
                select(Production.status, func.count()).group_by(Production.status)
            )
            .tuples()
            .all()
        )

    def sync_counts(self) -> dict[str, int]:
        return dict(
            self.session.execute(
                select(SyncJob.status, func.count()).group_by(SyncJob.status)
            )
            .tuples()
            .all()
        )

    def productions(self, query: ProductionQuery) -> tuple[list[Production], int]:
        filters = [] if query.status is None else [Production.status == query.status]
        total = (
            self.session.scalar(
                select(func.count()).select_from(Production).where(*filters)
            )
            or 0
        )
        items = self.session.scalars(
            select(Production)
            .where(*filters)
            .order_by(Production.created_at.desc(), Production.id.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        return list(items), total

    def sync_jobs(self, query: SyncQuery) -> tuple[list[SyncJob], int]:
        filters = [] if query.status is None else [SyncJob.status == query.status]
        total = (
            self.session.scalar(
                select(func.count()).select_from(SyncJob).where(*filters)
            )
            or 0
        )
        items = self.session.scalars(
            select(SyncJob)
            .where(*filters)
            .order_by(SyncJob.started_at.desc().nulls_last(), SyncJob.id.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        return list(items), total
