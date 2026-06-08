"""add city/state/cep/neighborhood to shelters

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-07

`city` and `state` are required for any meaningful location/mapping feature, so
they land as NOT NULL with a temporary server_default so existing rows are
backfilled to a placeholder. After backfill the default is dropped — new
inserts must provide the values explicitly. `cep` and `neighborhood` are
optional.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


brazilian_state_enum = postgresql.ENUM(
    name="brazilian_state",
    create_type=False,
)


def upgrade() -> None:
    op.add_column(
        "shelters",
        sa.Column(
            "city",
            sa.VARCHAR(),
            nullable=False,
            server_default="Unknown",
        ),
    )
    op.alter_column("shelters", "city", server_default=None)

    op.add_column(
        "shelters",
        sa.Column(
            "state",
            brazilian_state_enum,
            nullable=False,
            server_default="SP",
        ),
    )
    op.alter_column("shelters", "state", server_default=None)

    op.add_column(
        "shelters",
        sa.Column("neighborhood", sa.VARCHAR(), nullable=True),
    )
    op.add_column(
        "shelters",
        sa.Column("cep", sa.VARCHAR(), nullable=True),
    )

    op.create_index("ix_shelters_city_state", "shelters", ["city", "state"])


def downgrade() -> None:
    op.drop_index("ix_shelters_city_state", table_name="shelters")
    op.drop_column("shelters", "cep")
    op.drop_column("shelters", "neighborhood")
    op.drop_column("shelters", "state")
    op.drop_column("shelters", "city")
