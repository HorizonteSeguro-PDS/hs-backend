"""split beneficiary stay history into shelter_stays

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-07

Until now `beneficiaries` carried shelter_id + checked_in_at + checked_out_at,
which collapses the history of one person into a single row. To support a
future movement dashboard ("Maria foi do abrigo A pro B em DD/MM"), this
migration:

  1. Creates `shelter_stays(beneficiary_id, shelter_id, checked_in_at,
     checked_out_at)` — one row per check-in.
  2. Migrates existing data from beneficiaries into shelter_stays.
  3. Drops `shelter_id`, `checked_in_at`, `checked_out_at` from beneficiaries.

After this migration, a beneficiary is the canonical "person" record; their
current shelter is derived from the most recent shelter_stay with
`checked_out_at IS NULL`.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shelter_stays",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("beneficiary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "checked_in_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("checked_out_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["beneficiary_id"],
            ["beneficiaries.id"],
            name="fk_shelter_stays_beneficiary_id_beneficiaries",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name="fk_shelter_stays_shelter_id_shelters",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_shelter_stays_beneficiary_id", "shelter_stays", ["beneficiary_id"]
    )
    op.create_index("ix_shelter_stays_shelter_id", "shelter_stays", ["shelter_id"])
    # Partial index for fast "active stays" lookup (open-ended)
    op.create_index(
        "ix_shelter_stays_open",
        "shelter_stays",
        ["shelter_id", "checked_in_at"],
        postgresql_where=sa.text("checked_out_at IS NULL"),
    )

    # Migrate existing data: one stay row per beneficiary
    op.execute(
        """
        INSERT INTO shelter_stays
            (beneficiary_id, shelter_id, checked_in_at, checked_out_at)
        SELECT id, shelter_id, checked_in_at, checked_out_at
        FROM beneficiaries
        WHERE shelter_id IS NOT NULL
        """
    )

    # Drop the columns from beneficiaries — history lives in shelter_stays now
    op.drop_index("ix_beneficiaries_shelter_id", table_name="beneficiaries")
    op.drop_constraint(
        "fk_beneficiaries_shelter_id_shelters",
        "beneficiaries",
        type_="foreignkey",
    )
    op.drop_column("beneficiaries", "shelter_id")
    op.drop_column("beneficiaries", "checked_in_at")
    op.drop_column("beneficiaries", "checked_out_at")


def downgrade() -> None:
    op.add_column(
        "beneficiaries",
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "beneficiaries",
        sa.Column(
            "checked_in_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "beneficiaries",
        sa.Column("checked_out_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Best-effort restore: most recent stay per beneficiary
    op.execute(
        """
        UPDATE beneficiaries b
        SET shelter_id = s.shelter_id,
            checked_in_at = s.checked_in_at,
            checked_out_at = s.checked_out_at
        FROM (
            SELECT DISTINCT ON (beneficiary_id)
                beneficiary_id, shelter_id, checked_in_at, checked_out_at
            FROM shelter_stays
            ORDER BY beneficiary_id, checked_in_at DESC
        ) s
        WHERE b.id = s.beneficiary_id
        """
    )

    op.create_foreign_key(
        "fk_beneficiaries_shelter_id_shelters",
        "beneficiaries",
        "shelters",
        ["shelter_id"],
        ["id"],
    )
    op.create_index("ix_beneficiaries_shelter_id", "beneficiaries", ["shelter_id"])

    op.drop_index("ix_shelter_stays_open", table_name="shelter_stays")
    op.drop_index("ix_shelter_stays_shelter_id", table_name="shelter_stays")
    op.drop_index("ix_shelter_stays_beneficiary_id", table_name="shelter_stays")
    op.drop_table("shelter_stays")
