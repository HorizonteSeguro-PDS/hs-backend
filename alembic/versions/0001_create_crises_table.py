"""create crises table

Revision ID: 0001
Revises:
Create Date: 2026-05-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # gen_random_uuid() vem do core no PostgreSQL 13+, mas em versões
    # anteriores depende da extensão pgcrypto. Garante a função em qualquer caso.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "crises",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("flood", "fire", "landslide", "other", name="crisis_type"),
            nullable=False,
        ),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "closed", name="crisis_status"),
            nullable=False,
            server_default=sa.text("'active'::crisis_status"),
        ),
        sa.Column("state", sa.VARCHAR(2), nullable=False),
        sa.Column("city", sa.VARCHAR(), nullable=False),
        sa.Column("severity_initial", sa.SMALLINT(), nullable=True),
        sa.Column("severity_calculated", sa.SMALLINT(), nullable=True),
        sa.Column("severity_calculated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # TODO: add FK to users(id) once users table exists
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        # TODO: add FK to users(id) once users table exists
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("close_reason", sa.TEXT(), nullable=True),
        sa.CheckConstraint(
            "(severity_initial IS NULL OR (severity_initial >= 1 AND severity_initial <= 5))",
            name="ck_crises_severity_initial",
        ),
        sa.CheckConstraint(
            "(severity_calculated IS NULL OR (severity_calculated >= 1 AND severity_calculated <= 5))",
            name="ck_crises_severity_calculated",
        ),
    )

    op.create_index("ix_crises_state_city", "crises", ["state", "city"])
    op.create_index("ix_crises_status", "crises", ["status"])
    op.execute("CREATE INDEX ix_crises_created_at ON crises (created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_crises_created_at")
    op.drop_index("ix_crises_status", table_name="crises")
    op.drop_index("ix_crises_state_city", table_name="crises")
    op.drop_table("crises")

    op.execute("DROP TYPE IF EXISTS crisis_type")
    op.execute("DROP TYPE IF EXISTS crisis_status")
