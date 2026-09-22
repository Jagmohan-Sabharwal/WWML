"""Add persisted productions for workspace reads."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_productions"
down_revision: str | Sequence[str] | None = "0006_asset_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "productions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
        sa.CheckConstraint(
            "status IN ('draft', 'in_production', 'completed', 'archived')",
            name="status_valid",
        ),
    )
    op.create_index("ix_productions_created_id", "productions", ["created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_productions_created_id", table_name="productions")
    op.drop_table("productions")
