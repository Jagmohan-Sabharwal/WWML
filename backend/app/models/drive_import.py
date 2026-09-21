"""Durable ingestion progress, keyed by source file and provider version."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DriveImport(Base):
    __tablename__ = "drive_imports"
    __table_args__ = (
        UniqueConstraint("file_id", "source_version"),
        CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        CheckConstraint(
            "status IN ('watch', 'import', 'rename', 'register', "
            "'done', 'failed', 'skipped')",
            name="status_valid",
        ),
        Index("ix_drive_imports_created_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    file_id: Mapped[str] = mapped_column(String(256))
    source_version: Mapped[str] = mapped_column(String(256))
    source_name: Mapped[str] = mapped_column(String(1024))
    status: Mapped[str] = mapped_column(String(16), default="watch")
    attempts: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
