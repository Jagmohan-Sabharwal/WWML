"""Ordered production planning and explicit registry asset selections."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrderedNode(Base):
    """Shared fields for sibling-ordered production planning records."""

    __abstract__ = True
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProductionSequence(OrderedNode):
    __tablename__ = "production_sequences"
    __table_args__ = (
        UniqueConstraint("production_id", "position"),
        CheckConstraint("position > 0", name="position_positive"),
        CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
    )
    production_id: Mapped[UUID] = mapped_column(
        ForeignKey("productions.id", ondelete="RESTRICT")
    )


class Scene(OrderedNode):
    __tablename__ = "scenes"
    __table_args__ = (
        UniqueConstraint("sequence_id", "position"),
        CheckConstraint("position > 0", name="position_positive"),
        CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
    )
    sequence_id: Mapped[UUID] = mapped_column(
        ForeignKey("production_sequences.id", ondelete="RESTRICT")
    )


class Shot(OrderedNode):
    __tablename__ = "shots"
    __table_args__ = (
        UniqueConstraint("scene_id", "position"),
        CheckConstraint("position > 0", name="position_positive"),
        CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
    )
    scene_id: Mapped[UUID] = mapped_column(ForeignKey("scenes.id", ondelete="RESTRICT"))


class RequiredAsset(OrderedNode):
    """One editorial need, satisfied by at most one explicit asset selection."""

    __tablename__ = "required_assets"
    __table_args__ = (
        UniqueConstraint("shot_id", "position"),
        CheckConstraint("position > 0", name="position_positive"),
        CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
        CheckConstraint(
            "media_type IN ('video', 'audio', 'image', 'document', 'other')",
            name="media_type_valid",
        ),
    )
    shot_id: Mapped[UUID] = mapped_column(ForeignKey("shots.id", ondelete="RESTRICT"))
    media_type: Mapped[str] = mapped_column(String(16))


class LockedAsset(Base):
    """Preserve a chosen file version without copying or regenerating media."""

    __tablename__ = "locked_assets"
    __table_args__ = (
        CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name="checksum_format"),
        CheckConstraint("length(trim(storage_uri)) > 0", name="storage_uri_nonempty"),
    )
    required_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("required_assets.id", ondelete="RESTRICT"), primary_key=True
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"), index=True
    )
    checksum: Mapped[str] = mapped_column(String(64))
    storage_uri: Mapped[str] = mapped_column(Text)
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
