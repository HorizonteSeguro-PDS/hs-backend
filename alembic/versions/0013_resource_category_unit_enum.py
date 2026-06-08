"""convert resource_categories.unit from VARCHAR to resource_unit PG enum

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-07

`unit` was free-text. Locking it down to a closed set:
  kg | g | L | mL | unidade | real

Existing rows with values outside this set are normalised to 'unidade' (safe
default) before the type conversion so the ALTER doesn't fail on legacy data.
"""

from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


resource_unit_enum = postgresql.ENUM(
    "kg",
    "g",
    "L",
    "mL",
    "unidade",
    "real",
    name="resource_unit",
    create_type=False,
)


def upgrade() -> None:
    resource_unit_enum.create(op.get_bind(), checkfirst=True)

    # Normalise any pre-existing free-text unit that doesn't match the enum
    op.execute(
        """
        UPDATE resource_categories
        SET unit = 'unidade'
        WHERE unit NOT IN ('kg', 'g', 'L', 'mL', 'unidade', 'real')
        """
    )

    op.execute(
        "ALTER TABLE resource_categories "
        "ALTER COLUMN unit TYPE resource_unit "
        "USING unit::text::resource_unit"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE resource_categories "
        "ALTER COLUMN unit TYPE VARCHAR "
        "USING unit::text"
    )
    resource_unit_enum.drop(op.get_bind(), checkfirst=True)
