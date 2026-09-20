"""Reusable source assets for documentary production."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Asset(Base):
    """A stored file; its canonical SHA-256 prevents byte-identical duplicates."""

    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_nonnegative"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="sha256_format"),
        CheckConstraint("length(btrim(name)) > 0", name="name_nonempty"),
        CheckConstraint("length(btrim(storage_uri)) > 0", name="storage_uri_nonempty"),
        CheckConstraint(
            "media_type IN ('video', 'audio', 'image', 'document', 'other')",
            name="media_type_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    storage_uri: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(16), index=True)
    mime_type: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    asset_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
