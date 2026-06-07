"""multi role refactor: user_role enum + user_roles junction; drop users.role_id and roles

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


user_role_enum = postgresql.ENUM(
    "dev",
    "crisis_manager",
    "shelter_manager",
    "sheltered",
    name="user_role",
    create_type=False,
)


def upgrade() -> None:
    user_role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", user_role_enum, nullable=False),
        sa.Column(
            "granted_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name="pk_user_roles"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_roles_user_id_users",
            ondelete="CASCADE",
        ),
    )

    # Migrate existing data:
    #   master    -> dev
    #   standard  -> crisis_manager
    #   oversight -> crisis_manager   (oversight unified with crisis_manager)
    op.execute(
        """
        INSERT INTO user_roles (user_id, role)
        SELECT u.id,
               CASE r.name
                   WHEN 'master'    THEN 'dev'::user_role
                   WHEN 'standard'  THEN 'crisis_manager'::user_role
                   WHEN 'oversight' THEN 'crisis_manager'::user_role
                   ELSE NULL
               END AS new_role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE r.name IN ('master', 'standard', 'oversight')
        ON CONFLICT (user_id, role) DO NOTHING
        """
    )

    op.drop_constraint("fk_users_role_id_roles", "users", type_="foreignkey")
    op.drop_column("users", "role_id")

    op.drop_table("roles")


def downgrade() -> None:
    # Recreate roles table (without populating; lossy by design — dev-only flow)
    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column(
            "scope",
            postgresql.ENUM(name="role_scope", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )

    op.add_column(
        "users",
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_role_id_roles",
        "users",
        "roles",
        ["role_id"],
        ["id"],
    )

    op.drop_table("user_roles")
    user_role_enum.drop(op.get_bind(), checkfirst=True)
