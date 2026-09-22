"""Persistence primitives for planning records and serialized selections."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.api.workspace.schemas import PageQuery
from app.db.base import Base
from app.models.production_structure import LockedAsset, OrderedNode


class PlanningRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get[T: Base](
        self, model: type[T], identifier: UUID, *, lock: bool = False
    ) -> T | None:
        return self.session.get(model, identifier, with_for_update=lock)

    def children[T: OrderedNode](
        self,
        model: type[T],
        parent_column: InstrumentedAttribute[UUID],
        parent_id: UUID,
        query: PageQuery,
    ) -> tuple[list[T], int]:
        predicate = parent_column == parent_id
        total = (
            self.session.scalar(
                select(func.count()).select_from(model).where(predicate)
            )
            or 0
        )
        items = self.session.scalars(
            select(model)
            .where(predicate)
            .order_by(model.position, model.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        ).all()
        return list(items), total

    def add(self, row: Base) -> None:
        self.session.add(row)

    def remove_lock(self, row: LockedAsset) -> None:
        self.session.delete(row)
