"""add password_hash to users

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add as nullable first to support existing rows (dev DB may already have users),
    # then enforce NOT NULL after backfilling. In a fresh DB the table is empty
    # so the NOT NULL flip is a no-op on data.
    op.add_column(
        "users",
        sa.Column("password_hash", sa.VARCHAR(), nullable=True),
    )
    # Defensive: if there are pre-existing rows, give them a placeholder hash
    # that nobody can authenticate against. Operators will need to reset those.
    op.execute(
        "UPDATE users SET password_hash = '!disabled!' WHERE password_hash IS NULL"
    )
    op.alter_column("users", "password_hash", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "password_hash")
