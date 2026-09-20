"""Create the reusable assets registry.

Revision ID: 0001_create_assets
Revises: none
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_create_assets"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create assets with database-enforced file identity and valid metadata."""
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(16), nullable=False),
        sa.Column("mime_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "asset_metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assets"),
        sa.UniqueConstraint("sha256", name="uq_assets_sha256"),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_assets_size_nonnegative")),
        sa.CheckConstraint(
            "sha256 ~ '^[0-9a-f]{64}$'", name=op.f("ck_assets_sha256_format")
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0", name=op.f("ck_assets_name_nonempty")
        ),
        sa.CheckConstraint(
            "length(btrim(storage_uri)) > 0",
            name=op.f("ck_assets_storage_uri_nonempty"),
        ),
        sa.CheckConstraint(
            "media_type IN ('video', 'audio', 'image', 'document', 'other')",
            name=op.f("ck_assets_media_type_valid"),
        ),
    )
    op.create_index("ix_assets_media_type", "assets", ["media_type"])


def downgrade() -> None:
    """Remove assets; this deliberately deletes all registered asset records."""
    op.drop_index("ix_assets_media_type", table_name="assets")
    op.drop_table("assets")
