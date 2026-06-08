"""add contact/profile fields to shelters

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-07

Adds optional contact and profile fields used by the shelter creation form:
  - email                  -> contato externo do abrigo
  - phone                  -> telefone de contato
  - entry_requirements     -> regras de entrada (texto livre)
  - attended_special_needs -> público atendido / vulnerabilidades suportadas
  - bio                    -> descricao livre do abrigo

Todas nullable porque o front pode criar abrigo emergencial sem todos preenchidos.
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shelters",
        sa.Column("email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "shelters",
        sa.Column("phone", sa.VARCHAR(), nullable=True),
    )
    op.add_column(
        "shelters",
        sa.Column("entry_requirements", sa.VARCHAR(), nullable=True),
    )
    op.add_column(
        "shelters",
        sa.Column("attended_special_needs", sa.VARCHAR(), nullable=True),
    )
    op.add_column(
        "shelters",
        sa.Column("bio", sa.VARCHAR(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shelters", "bio")
    op.drop_column("shelters", "attended_special_needs")
    op.drop_column("shelters", "entry_requirements")
    op.drop_column("shelters", "phone")
    op.drop_column("shelters", "email")
