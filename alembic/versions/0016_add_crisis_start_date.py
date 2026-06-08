"""add start_date to crises

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-08
"""

import sqlalchemy as sa
from alembic import op


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("crises", sa.Column("start_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("crises", "start_date")
