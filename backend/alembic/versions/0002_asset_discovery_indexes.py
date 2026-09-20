"""Index ordered asset discovery with optional media and MIME filters.

Revision ID: 0002_asset_discovery
Revises: 0001_create_assets
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_asset_discovery"
down_revision: str | Sequence[str] | None = "0001_create_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite indexes; no registered asset data is changed."""
    op.create_index("ix_assets_created_id", "assets", ["created_at", "id"])
    op.create_index(
        "ix_assets_media_created_id", "assets", ["media_type", "created_at", "id"]
    )
    op.create_index(
        "ix_assets_mime_created_id", "assets", ["mime_type", "created_at", "id"]
    )
    op.drop_index("ix_assets_media_type", table_name="assets")


def downgrade() -> None:
    """Restore the previous indexes while preserving every asset record."""
    op.create_index("ix_assets_media_type", "assets", ["media_type"])
    op.drop_index("ix_assets_mime_created_id", table_name="assets")
    op.drop_index("ix_assets_media_created_id", table_name="assets")
    op.drop_index("ix_assets_created_id", table_name="assets")
