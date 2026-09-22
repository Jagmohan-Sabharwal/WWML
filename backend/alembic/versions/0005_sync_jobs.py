"""Add synchronization run history without changing assets or per-file records."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_sync_jobs"
down_revision: str | Sequence[str] | None = "0004_asset_soft_delete"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sync_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("files_scanned", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "files_imported", sa.BigInteger(), server_default="0", nullable=False
        ),
        sa.Column("files_skipped", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "errors",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', "
            "'completed_with_errors', 'failed')",
            name="status_valid",
        ),
        sa.CheckConstraint(
            "files_scanned >= 0 AND files_imported >= 0 AND files_skipped >= 0",
            name="counters_nonnegative",
        ),
        sa.CheckConstraint(
            "files_imported + files_skipped <= files_scanned",
            name="counters_consistent",
        ),
        sa.CheckConstraint("jsonb_typeof(errors) = 'array'", name="errors_array"),
        sa.CheckConstraint(
            "(status = 'pending' AND started_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'running' AND started_at IS NOT NULL "
            "AND completed_at IS NULL) OR "
            "(status IN ('completed', 'completed_with_errors', 'failed') "
            "AND started_at IS NOT NULL AND completed_at IS NOT NULL "
            "AND completed_at >= started_at)",
            name="lifecycle_valid",
        ),
    )
    op.create_index("ix_sync_jobs_started_id", "sync_jobs", ["started_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_sync_jobs_started_id", table_name="sync_jobs")
    op.drop_table("sync_jobs")
