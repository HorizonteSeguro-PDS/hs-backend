"""drop sheltered value from user_role enum

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-07

PostgreSQL does not support `ALTER TYPE ... DROP VALUE`, so we swap-and-replace:
rename the current enum, create a new one without the value, convert the column
to the new type, drop the old enum.

Rows that referenced the dropped value are removed first.
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Remove any user_roles rows referencing the value being dropped.
    op.execute("DELETE FROM user_roles WHERE role = 'sheltered'::user_role")

    # 2. Rename current enum so we can free up the original name.
    op.execute("ALTER TYPE user_role RENAME TO user_role_old")

    # 3. Create the new enum without 'sheltered'.
    op.execute(
        "CREATE TYPE user_role AS ENUM ('dev', 'crisis_manager', 'shelter_manager')"
    )

    # 4. Move the column over to the new enum type.
    op.execute(
        "ALTER TABLE user_roles "
        "ALTER COLUMN role TYPE user_role "
        "USING role::text::user_role"
    )

    # 5. Drop the old enum.
    op.execute("DROP TYPE user_role_old")


def downgrade() -> None:
    op.execute("ALTER TYPE user_role RENAME TO user_role_old")
    op.execute(
        "CREATE TYPE user_role AS ENUM "
        "('dev', 'crisis_manager', 'shelter_manager', 'sheltered')"
    )
    op.execute(
        "ALTER TABLE user_roles "
        "ALTER COLUMN role TYPE user_role "
        "USING role::text::user_role"
    )
    op.execute("DROP TYPE user_role_old")
