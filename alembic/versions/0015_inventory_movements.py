"""create inventory_movements table + movement enums

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-07

Each row in `inventory_movements` is one IN/OUT event on a shelter's stock.
Immutable: corrections are themselves new movements (`adjustment`). Drives the
movement dashboard and is the source-of-truth from which `inventory_items`
is updated as a cache.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


movement_direction_enum = postgresql.ENUM(
    "in",
    "out",
    name="movement_direction",
    create_type=False,
)
movement_reason_enum = postgresql.ENUM(
    "donation",
    "distribution",
    "transfer_in",
    "transfer_out",
    "adjustment",
    "expired",
    "other",
    name="movement_reason",
    create_type=False,
)


def upgrade() -> None:
    movement_direction_enum.create(op.get_bind(), checkfirst=True)
    movement_reason_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "inventory_movements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", movement_direction_enum, nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", movement_reason_enum, nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name="fk_inventory_movements_shelter_id_shelters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["resource_categories.id"],
            name="fk_inventory_movements_category_id_resource_categories",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_inventory_movements_created_by_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_inventory_movements_quantity_positive",
        ),
    )

    op.create_index(
        "ix_inventory_movements_shelter_id",
        "inventory_movements",
        ["shelter_id"],
    )
    op.create_index(
        "ix_inventory_movements_shelter_created_at",
        "inventory_movements",
        ["shelter_id", "created_at"],
    )
    op.create_index(
        "ix_inventory_movements_category_id",
        "inventory_movements",
        ["category_id"],
    )
    op.create_index(
        "ix_inventory_movements_created_by",
        "inventory_movements",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_created_by", table_name="inventory_movements")
    op.drop_index(
        "ix_inventory_movements_category_id", table_name="inventory_movements"
    )
    op.drop_index(
        "ix_inventory_movements_shelter_created_at",
        table_name="inventory_movements",
    )
    op.drop_index("ix_inventory_movements_shelter_id", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    movement_reason_enum.drop(op.get_bind(), checkfirst=True)
    movement_direction_enum.drop(op.get_bind(), checkfirst=True)
