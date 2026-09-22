"""Add ordered planning hierarchy and locked registry selections."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_production_structure"
down_revision: str | Sequence[str] | None = "0007_productions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table, parent_column, parent_table in (
        ("production_sequences", "production_id", "productions"),
        ("scenes", "sequence_id", "production_sequences"),
        ("shots", "scene_id", "scenes"),
        ("required_assets", "shot_id", "shots"),
    ):
        extras: list[sa.SchemaItem] = []
        if table == "required_assets":
            extras = [
                sa.Column("media_type", sa.String(16), nullable=False),
                sa.CheckConstraint(
                    "media_type IN ('video', 'audio', 'image', 'document', 'other')",
                    name="media_type_valid",
                ),
            ]
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(parent_column, sa.Uuid(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                [parent_column], [f"{parent_table}.id"], ondelete="RESTRICT"
            ),
            sa.UniqueConstraint(parent_column, "position"),
            sa.CheckConstraint("position > 0", name="position_positive"),
            sa.CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
            *extras,
        )
    op.create_table(
        "locked_assets",
        sa.Column("required_asset_id", sa.Uuid(), primary_key=True),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["required_asset_id"], ["required_assets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("checksum ~ '^[0-9a-f]{64}$'", name="checksum_format"),
        sa.CheckConstraint(
            "length(trim(storage_uri)) > 0", name="storage_uri_nonempty"
        ),
    )
    op.create_index("ix_locked_assets_asset_id", "locked_assets", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_locked_assets_asset_id", table_name="locked_assets")
    for table in (
        "locked_assets",
        "required_assets",
        "shots",
        "scenes",
        "production_sequences",
    ):
        op.drop_table(table)
