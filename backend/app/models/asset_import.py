"""Import provenance links source files, canonical assets and synchronization runs."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AssetImport(Base):
    """One source-file registration per sync run, with a checksum snapshot."""

    __tablename__ = "asset_imports"
    __table_args__ = (
        PrimaryKeyConstraint("sync_job_id", "google_drive_file_id"),
        CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name="checksum_format"),
        CheckConstraint(
            "google_drive_file_id ~ '^[A-Za-z0-9_-]+$'",
            name="drive_file_id_format",
        ),
        Index("ix_asset_imports_asset_date", "asset_id", "import_date"),
        Index("ix_asset_imports_source_date", "google_drive_file_id", "import_date"),
    )

    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    google_drive_file_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    import_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    sync_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("sync_jobs.id", ondelete="RESTRICT"),
        primary_key=True,
    )
