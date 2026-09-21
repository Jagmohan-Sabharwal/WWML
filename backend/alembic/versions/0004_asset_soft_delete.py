"""Preserve canonical asset registrations through soft deletion.

Revision ID: 0004_asset_soft_delete
Revises: 0003_drive_imports
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_asset_soft_delete"
down_revision: str | Sequence[str] | None = "0003_drive_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Existing records remain active; no content or foreign keys are changed."""
    op.add_column(
        "assets", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_assets_active_created_id",
        "assets",
        ["created_at", "id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    """Preserve rows, but removal of deletion timestamps makes all rows active."""
    op.drop_index("ix_assets_active_created_id", table_name="assets")
    op.drop_column("assets", "deleted_at")
