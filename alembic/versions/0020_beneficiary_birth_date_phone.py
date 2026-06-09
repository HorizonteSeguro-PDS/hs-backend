"""add birth_date and phone to beneficiaries

Modal de check-in do front coleta nome, CPF, data de nascimento e telefone.
Os dois primeiros ja existem; aqui adicionamos os ultimos dois.

`age` permanece como coluna stored (existing seed/data depende). Quando o
gestor preenche birth_date no check-in, o backend tambem deriva e popula o
age (apenas pra acelerar leituras — birth_date é a fonte da verdade).

Revision ID: 0020
Revises: 0019
Create Date: 2026-06-09
"""

import sqlalchemy as sa
from alembic import op


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "beneficiaries",
        sa.Column("birth_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "beneficiaries",
        sa.Column("phone", sa.VARCHAR(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("beneficiaries", "phone")
    op.drop_column("beneficiaries", "birth_date")
