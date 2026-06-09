"""drop latitude/longitude from crises

Revisão da decisão da 0019: a granularidade geográfica fica em shelter
(que ja tem lat/long), não em crisis. Crise é vista no mapa pelo aglomerado
dos seus abrigos.

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_crises_longitude_range", "crises", type_="check")
    op.drop_constraint("ck_crises_latitude_range", "crises", type_="check")
    op.drop_column("crises", "longitude")
    op.drop_column("crises", "latitude")


def downgrade() -> None:
    op.add_column("crises", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("crises", sa.Column("longitude", sa.Float(), nullable=True))
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
