"""crises_shelters M2M; drop shelters.crisis_id

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crises_shelters",
        sa.Column("crisis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("crisis_id", "shelter_id", name="pk_crises_shelters"),
        sa.ForeignKeyConstraint(
            ["crisis_id"],
            ["crises.id"],
            name="fk_crises_shelters_crisis_id_crises",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name="fk_crises_shelters_shelter_id_shelters",
            ondelete="CASCADE",
        ),
    )

    # Migrate existing relations from the singular shelters.crisis_id column
    op.execute(
        """
        INSERT INTO crises_shelters (crisis_id, shelter_id)
        SELECT s.crisis_id, s.id
        FROM shelters s
        WHERE s.crisis_id IS NOT NULL
        ON CONFLICT (crisis_id, shelter_id) DO NOTHING
        """
    )

    op.drop_constraint(
        "fk_shelters_crisis_id_crises",
        "shelters",
        type_="foreignkey",
    )
    op.drop_index("ix_shelters_crisis_id", table_name="shelters")
    op.drop_column("shelters", "crisis_id")


def downgrade() -> None:
    op.add_column(
        "shelters",
        sa.Column("crisis_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shelters_crisis_id_crises",
        "shelters",
        "crises",
        ["crisis_id"],
        ["id"],
    )
    op.create_index("ix_shelters_crisis_id", "shelters", ["crisis_id"])

    # Best-effort restore (picks an arbitrary crisis per shelter if multiple)
    op.execute(
        """
        UPDATE shelters s
        SET crisis_id = cs.crisis_id
        FROM (
            SELECT DISTINCT ON (shelter_id) shelter_id, crisis_id
            FROM crises_shelters
            ORDER BY shelter_id, joined_at ASC
        ) cs
        WHERE s.id = cs.shelter_id
        """
    )

    op.drop_table("crises_shelters")
