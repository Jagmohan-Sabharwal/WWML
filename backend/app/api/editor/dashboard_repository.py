"""Database projections for production readiness and shared-library activity."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models import Asset, DriveImport, Production, SyncJob
from app.models.production_structure import (
    LockedAsset,
    ProductionSequence,
    RequiredAsset,
    Scene,
    Shot,
)


@dataclass(frozen=True)
class DashboardFacts:
    production: Production
    required: int
    ready: int
    missing: int
    unplanned: int
    queue: int
    failed: int
    latest: list[DriveImport]
    job: SyncJob | None


class DashboardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def read(self, identifier: UUID) -> DashboardFacts | None:
        session = self.session
        production = session.get(Production, identifier)
        if production is None:
            return None
        ready = and_(
            LockedAsset.required_asset_id.is_not(None),
            Asset.id.is_not(None),
            Asset.deleted_at.is_(None),
            Asset.media_type == RequiredAsset.media_type,
            Asset.sha256 == LockedAsset.checksum,
            Asset.storage_uri == LockedAsset.storage_uri,
        )
        statement = (
            select(
                func.count(RequiredAsset.id),
                func.coalesce(func.sum(case((ready, 1), else_=0)), 0),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    RequiredAsset.id.is_not(None),
                                    LockedAsset.required_asset_id.is_(None),
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(case((RequiredAsset.id.is_(None), 1), else_=0)), 0
                ),
            )
            .select_from(ProductionSequence)
            .join(Scene, Scene.sequence_id == ProductionSequence.id)
            .join(Shot, Shot.scene_id == Scene.id)
            .outerjoin(RequiredAsset, RequiredAsset.shot_id == Shot.id)
            .outerjoin(LockedAsset, LockedAsset.required_asset_id == RequiredAsset.id)
            .outerjoin(Asset, Asset.id == LockedAsset.asset_id)
            .where(ProductionSequence.production_id == identifier)
        )
        required, ready_count, missing, unplanned = (
            int(value) for value in session.execute(statement).one()
        )
        queue = (
            session.scalar(
                select(func.count())
                .select_from(DriveImport)
                .where(
                    DriveImport.status.in_(["watch", "import", "rename", "register"])
                )
            )
            or 0
        )
        failed = (
            session.scalar(
                select(func.count())
                .select_from(DriveImport)
                .where(DriveImport.status == "failed")
            )
            or 0
        )
        latest = session.scalars(
            select(DriveImport)
            .where(DriveImport.status == "done")
            .order_by(DriveImport.updated_at.desc(), DriveImport.id.desc())
            .limit(5)
        ).all()
        job = session.scalars(
            select(SyncJob)
            .order_by(SyncJob.started_at.desc().nulls_last(), SyncJob.id.desc())
            .limit(1)
        ).first()
        return DashboardFacts(
            production,
            required,
            ready_count,
            missing,
            unplanned,
            queue,
            failed,
            list(latest),
            job,
        )
