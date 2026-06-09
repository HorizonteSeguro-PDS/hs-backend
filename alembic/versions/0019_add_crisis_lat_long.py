"""add latitude/longitude to crises

Permite que o front plote a crise no mapa. Nullable porque crises antigas
nao têm coordenadas e nao queremos backfillar arbitrariamente.

CHECK constraints validam o range geografico (lat -90..90, long -180..180).

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "crises",
        sa.Column("latitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "crises",
        sa.Column("longitude", sa.Float(), nullable=True),
    )
    op.create_check_constraint(
        "ck_crises_latitude_range",
        "crises",
        "(latitude IS NULL OR (latitude >= -90 AND latitude <= 90))",
    )
    op.create_check_constraint(
        "ck_crises_longitude_range",
        "crises",
        "(longitude IS NULL OR (longitude >= -180 AND longitude <= 180))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_crises_longitude_range", "crises", type_="check")
    op.drop_constraint("ck_crises_latitude_range", "crises", type_="check")
    op.drop_column("crises", "longitude")
    op.drop_column("crises", "latitude")
