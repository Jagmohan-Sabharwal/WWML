"""Run-level synchronization history, separate from per-file import progress."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncJob(Base):
    """Persist counters and safe error summaries for a single synchronization run."""

    __tablename__ = "sync_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', "
            "'completed_with_errors', 'failed')",
            name="status_valid",
        ),
        CheckConstraint(
            "files_scanned >= 0 AND files_imported >= 0 AND files_skipped >= 0",
            name="counters_nonnegative",
        ),
        CheckConstraint(
            "files_imported + files_skipped <= files_scanned",
            name="counters_consistent",
        ),
        CheckConstraint("jsonb_typeof(errors) = 'array'", name="errors_array"),
        CheckConstraint(
            "(status = 'pending' AND started_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status IN ('completed', 'completed_with_errors', 'failed') "
            "AND started_at IS NOT NULL AND completed_at IS NOT NULL "
            "AND completed_at >= started_at)",
            name="lifecycle_valid",
        ),
        Index("ix_sync_jobs_started_id", "started_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    files_scanned: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    files_imported: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    files_skipped: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    errors: Mapped[list[dict[str, str]]] = mapped_column(
        MutableList.as_mutable(JSONB), default=list, server_default=text("'[]'::jsonb")
    )
