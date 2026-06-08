"""add cpf to beneficiaries — primary search key on the frontend

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-07

CPF (Cadastro de Pessoas Físicas) is the canonical Brazilian individual id and
will be the primary search axis on the frontend. Stored as VARCHAR (digits
only or formatted — application normalises) with a partial unique constraint:
two beneficiaries cannot have the same non-null CPF. NULL allowed for
undocumented / foreign beneficiaries.
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "beneficiaries",
        sa.Column("cpf", sa.VARCHAR(length=14), nullable=True),
    )
    # Partial unique: NULL CPFs don't conflict (multiple unknowns allowed),
    # but a non-null CPF must be unique.
    op.create_index(
        "uq_beneficiaries_cpf",
        "beneficiaries",
        ["cpf"],
        unique=True,
        postgresql_where=sa.text("cpf IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_beneficiaries_cpf", table_name="beneficiaries")
    op.drop_column("beneficiaries", "cpf")
