"""beneficiaries.user_id optional FK to users

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "beneficiaries",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_beneficiaries_user_id_users",
        "beneficiaries",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_beneficiaries_user_id", "beneficiaries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_beneficiaries_user_id", table_name="beneficiaries")
    op.drop_constraint(
        "fk_beneficiaries_user_id_users",
        "beneficiaries",
        type_="foreignkey",
    )
    op.drop_column("beneficiaries", "user_id")
