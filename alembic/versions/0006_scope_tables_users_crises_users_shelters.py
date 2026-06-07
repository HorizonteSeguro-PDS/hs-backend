"""scope tables: users_crises and users_shelters

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users_crises",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("crisis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "granted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "crisis_id", name="pk_users_crises"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_users_crises_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["crisis_id"],
            ["crises.id"],
            name="fk_users_crises_crisis_id_crises",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name="fk_users_crises_granted_by_users",
        ),
    )

    op.create_table(
        "users_shelters",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "granted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "shelter_id", name="pk_users_shelters"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_users_shelters_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name="fk_users_shelters_shelter_id_shelters",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name="fk_users_shelters_granted_by_users",
        ),
    )


def downgrade() -> None:
    op.drop_table("users_shelters")
    op.drop_table("users_crises")
