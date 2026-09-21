"""Track restartable Google Drive ingestion without changing existing assets."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_drive_imports"
down_revision: str | Sequence[str] | None = "0002_asset_discovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drive_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.String(256), nullable=False),
        sa.Column("source_version", sa.String(256), nullable=False),
        sa.Column("source_name", sa.String(1024), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("asset_id", sa.Uuid()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_id", "source_version"),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="SET NULL"),
        sa.CheckConstraint("attempts >= 0", name="attempts_nonnegative"),
        sa.CheckConstraint(
            "status IN ('watch', 'import', 'rename', 'register', "
            "'done', 'failed', 'skipped')",
            name="status_valid",
        ),
    )
    op.create_index(
        "ix_drive_imports_created_id", "drive_imports", ["created_at", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_drive_imports_created_id", table_name="drive_imports")
    op.drop_table("drive_imports")
