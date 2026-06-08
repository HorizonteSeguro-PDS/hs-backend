"""rebase crisis severity scale from 1-5 to 0-3

Aligns the backend with the agreed labels exposed to the frontend:
    0 -> INATIVO
    1 -> BAIXA
    2 -> MÉDIA
    3 -> ALTA

Existing rows on the old 1-5 scale are remapped:
    1, 2 -> 1 (BAIXA)
    3    -> 2 (MÉDIA)
    4, 5 -> 3 (ALTA)

This is destructive in the sense that intermediate granularity is lost,
but it matches the new business rule (severity é o que o front exibe;
back só guarda número pra calcular).

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-08
"""

from alembic import op


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Drop old 1-5 CHECK constraints so the UPDATE pode rodar livre.
    op.drop_constraint("ck_crises_severity_initial", "crises", type_="check")
    op.drop_constraint("ck_crises_severity_calculated", "crises", type_="check")

    # 2) Remap existing data 1-5 -> 0-3.
    op.execute(
        """
        UPDATE crises
        SET severity_initial = CASE
            WHEN severity_initial IN (1, 2) THEN 1
            WHEN severity_initial = 3      THEN 2
            WHEN severity_initial IN (4, 5) THEN 3
            ELSE severity_initial
        END
        WHERE severity_initial IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE crises
        SET severity_calculated = CASE
            WHEN severity_calculated IN (1, 2) THEN 1
            WHEN severity_calculated = 3      THEN 2
            WHEN severity_calculated IN (4, 5) THEN 3
            ELSE severity_calculated
        END
        WHERE severity_calculated IS NOT NULL
        """
    )

    # 3) Recreate CHECK constraints on the new 0-3 range.
    op.create_check_constraint(
        "ck_crises_severity_initial",
        "crises",
        "(severity_initial IS NULL OR (severity_initial >= 0 AND severity_initial <= 3))",
    )
    op.create_check_constraint(
        "ck_crises_severity_calculated",
        "crises",
        "(severity_calculated IS NULL OR (severity_calculated >= 0 AND severity_calculated <= 3))",
    )


def downgrade() -> None:
    # Reverse the constraint swap. We DO NOT try to expand 0-3 back to 1-5
    # because the original distinction was lost on upgrade.
    op.drop_constraint("ck_crises_severity_initial", "crises", type_="check")
    op.drop_constraint("ck_crises_severity_calculated", "crises", type_="check")
    # Bump 0 -> 1 so the old constraint accepts every row.
    op.execute("UPDATE crises SET severity_initial = 1 WHERE severity_initial = 0")
    op.execute(
        "UPDATE crises SET severity_calculated = 1 WHERE severity_calculated = 0"
    )
    op.create_check_constraint(
        "ck_crises_severity_initial",
        "crises",
        "(severity_initial IS NULL OR (severity_initial >= 1 AND severity_initial <= 5))",
    )
    op.create_check_constraint(
        "ck_crises_severity_calculated",
        "crises",
        "(severity_calculated IS NULL OR (severity_calculated >= 1 AND severity_calculated <= 5))",
    )
