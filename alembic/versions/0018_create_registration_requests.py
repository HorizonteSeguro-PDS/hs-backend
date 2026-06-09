"""create registration requests

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registration_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "status",
            sa.VARCHAR(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("request_type", sa.VARCHAR(), nullable=False),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("email", sa.VARCHAR(), nullable=False),
        sa.Column("phone", sa.VARCHAR(), nullable=True),
        sa.Column("password_hash", sa.VARCHAR(), nullable=False),
        sa.Column("roles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("new_organization_name", sa.VARCHAR(), nullable=True),
        sa.Column("new_organization_cnpj", sa.VARCHAR(), nullable=True),
        sa.Column("new_organization_type", sa.VARCHAR(), nullable=True),
        sa.Column("new_organization_contact_email", sa.VARCHAR(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_organization_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_registration_requests_organization_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_registration_requests_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["created_organization_id"],
            ["organizations.id"],
            name="fk_registration_requests_created_organization_id",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            name="fk_registration_requests_reviewed_by_users",
        ),
    )
    op.create_index(
        "ix_registration_requests_status",
        "registration_requests",
        ["status"],
    )
    op.create_index(
        "ix_registration_requests_email_status",
        "registration_requests",
        ["email", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_registration_requests_email_status", table_name="registration_requests"
    )
    op.drop_index("ix_registration_requests_status", table_name="registration_requests")
    op.drop_table("registration_requests")
