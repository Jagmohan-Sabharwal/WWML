"""Join production-scoped requirements without per-row database requests."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.workspace.schemas import PageQuery
from app.models import Asset, Production
from app.models.production_structure import (
    LockedAsset,
    ProductionSequence,
    RequiredAsset,
    Scene,
    Shot,
)

type EditorRecord = tuple[
    ProductionSequence,
    Scene,
    Shot,
    RequiredAsset | None,
    LockedAsset | None,
    Asset | None,
]


class EditorRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def production(self, identifier: UUID) -> Production | None:
        return self.session.get(Production, identifier)

    def rows(
        self, production_id: UUID, query: PageQuery
    ) -> tuple[list[EditorRecord], int]:
        statement = (
            select(ProductionSequence, Scene, Shot, RequiredAsset, LockedAsset, Asset)
            .select_from(ProductionSequence)
            .join(Scene, Scene.sequence_id == ProductionSequence.id)
            .join(Shot, Shot.scene_id == Scene.id)
            .outerjoin(RequiredAsset, RequiredAsset.shot_id == Shot.id)
            .outerjoin(LockedAsset, LockedAsset.required_asset_id == RequiredAsset.id)
            .outerjoin(Asset, Asset.id == LockedAsset.asset_id)
            .where(ProductionSequence.production_id == production_id)
        )
        total = (
            self.session.scalar(select(func.count()).select_from(statement.subquery()))
            or 0
        )
        rows = self.session.execute(
            statement.order_by(
                ProductionSequence.position,
                Scene.position,
                Shot.position,
                RequiredAsset.position.asc().nulls_first(),
                Shot.id,
                RequiredAsset.id,
            )
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        return [
            (sequence, scene, shot, requirement, lock, asset)
            for sequence, scene, shot, requirement, lock, asset in rows
        ], total
