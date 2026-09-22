"""Add asset import provenance without modifying existing import workflows."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_asset_imports"
down_revision: str | Sequence[str] | None = "0005_sync_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_imports",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("google_drive_file_id", sa.String(256), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column(
            "import_date",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("sync_job_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("sync_job_id", "google_drive_file_id"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sync_job_id"], ["sync_jobs.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name="checksum_format"),
        sa.CheckConstraint(
            "google_drive_file_id ~ '^[A-Za-z0-9_-]+$'",
            name="drive_file_id_format",
        ),
    )
    op.create_index(
        "ix_asset_imports_asset_date", "asset_imports", ["asset_id", "import_date"]
    )
    op.create_index(
        "ix_asset_imports_source_date",
        "asset_imports",
        ["google_drive_file_id", "import_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_asset_imports_source_date", table_name="asset_imports")
    op.drop_index("ix_asset_imports_asset_date", table_name="asset_imports")
    op.drop_table("asset_imports")
