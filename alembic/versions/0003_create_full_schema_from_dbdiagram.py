"""create full schema from dbdiagram

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


role_scope = postgresql.ENUM(
    "global",
    "organization",
    "crisis",
    "shelter",
    name="role_scope",
    create_type=False,
)
organization_type = postgresql.ENUM(
    "crisis_manager",
    "shelter_operator",
    "donor",
    "mixed",
    "other",
    name="organization_type",
    create_type=False,
)
brazilian_state = postgresql.ENUM(
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
    name="brazilian_state",
    create_type=False,
)
shelter_type = postgresql.ENUM(
    "institutional",
    "community_home",
    "improvised_public",
    name="shelter_type",
    create_type=False,
)
shelter_status = postgresql.ENUM(
    "preparing",
    "active",
    "full",
    "closed",
    name="shelter_status",
    create_type=False,
)
shelter_need_status = postgresql.ENUM(
    "open",
    "partially_fulfilled",
    "fulfilled",
    "cancelled",
    name="shelter_need_status",
    create_type=False,
)
priority_level = postgresql.ENUM(
    "low",
    "medium",
    "high",
    "critical",
    name="priority_level",
    create_type=False,
)
vulnerability_type = postgresql.ENUM(
    "child",
    "elderly",
    "pregnant",
    "disabled",
    "chronic_illness",
    "none",
    "other",
    name="vulnerability_type",
    create_type=False,
)
donation_status = postgresql.ENUM(
    "pledged",
    "confirmed",
    "received",
    "distributed",
    "cancelled",
    name="donation_status",
    create_type=False,
)
transfer_type = postgresql.ENUM(
    "external_donation",
    "inter_shelter",
    name="transfer_type",
    create_type=False,
)
distribution_status = postgresql.ENUM(
    "planned",
    "dispatched",
    "delivered",
    "cancelled",
    name="distribution_status",
    create_type=False,
)
notification_type = postgresql.ENUM(
    "crisis_alert",
    "need_declared",
    "need_critical",
    "donation_pledged",
    "donation_received",
    "distribution_dispatched",
    "distribution_delivered",
    "shelter_full",
    "system",
    name="notification_type",
    create_type=False,
)
audit_action = postgresql.ENUM(
    "create",
    "update",
    "close",
    "reopen",
    "delete",
    "verify",
    "pledge",
    "confirm",
    "deliver",
    "cancel",
    "login",
    "logout",
    name="audit_action",
    create_type=False,
)
audit_entity_type = postgresql.ENUM(
    "ORGANIZATION",
    "USER",
    "ROLE",
    "CRISIS",
    "SHELTER",
    "BENEFICIARY",
    "SHELTER_NEED",
    "INVENTORY_ITEM",
    "DONATION",
    "DISTRIBUTION",
    "NOTIFICATION",
    name="audit_entity_type",
    create_type=False,
)

new_enums = (
    role_scope,
    organization_type,
    brazilian_state,
    shelter_type,
    shelter_status,
    shelter_need_status,
    priority_level,
    vulnerability_type,
    donation_status,
    transfer_type,
    distribution_status,
    notification_type,
    audit_action,
    audit_entity_type,
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE crisis_type ADD VALUE IF NOT EXISTS 'drought' AFTER 'landslide'"
        )
        op.execute(
            "ALTER TYPE crisis_type ADD VALUE IF NOT EXISTS 'storm' AFTER 'drought'"
        )
        op.execute(
            "ALTER TYPE crisis_type ADD VALUE IF NOT EXISTS 'epidemic' AFTER 'storm'"
        )
        op.execute(
            "ALTER TYPE crisis_status ADD VALUE IF NOT EXISTS 'draft' BEFORE 'active'"
        )
        op.execute(
            "ALTER TYPE crisis_status ADD VALUE IF NOT EXISTS 'archived' AFTER 'closed'"
        )

    bind = op.get_bind()

    for enum_type in new_enums:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("scope", role_scope, nullable=False),
        sa.Column(
            "permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )

    op.create_table(
        "organizations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("cnpj", sa.VARCHAR(), nullable=True),
        sa.Column("type", organization_type, nullable=False),
        sa.Column("contact_email", sa.VARCHAR(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("cnpj", name="uq_organizations_cnpj"),
    )

    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("email", sa.VARCHAR(), nullable=False),
        sa.Column("phone", sa.VARCHAR(), nullable=True),
        sa.Column(
            "verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name="fk_users_role_id_roles",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_users_organization_id_organizations",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.add_column(
        "crises",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        "ALTER TABLE crises "
        "ALTER COLUMN state TYPE brazilian_state "
        "USING state::text::brazilian_state"
    )
    op.create_foreign_key(
        "fk_crises_organization_id_organizations",
        "crises",
        "organizations",
        ["organization_id"],
        ["id"],
    )
    op.execute(
        "ALTER TABLE crises "
        "ADD CONSTRAINT fk_crises_created_by_users "
        "FOREIGN KEY (created_by) REFERENCES users (id) NOT VALID"
    )
    op.execute(
        "ALTER TABLE crises "
        "ADD CONSTRAINT fk_crises_closed_by_users "
        "FOREIGN KEY (closed_by) REFERENCES users (id) NOT VALID"
    )

    op.create_table(
        "shelters",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("crisis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("responsible_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("address", sa.VARCHAR(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column(
            "occupation",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("shelter_type", shelter_type, nullable=False),
        sa.Column(
            "status",
            shelter_status,
            nullable=False,
            server_default=sa.text("'preparing'::shelter_status"),
        ),
        sa.Column(
            "verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
        sa.ForeignKeyConstraint(
            ["crisis_id"],
            ["crises.id"],
            name="fk_shelters_crisis_id_crises",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_shelters_organization_id_organizations",
        ),
        sa.ForeignKeyConstraint(
            ["responsible_user_id"],
            ["users.id"],
            name="fk_shelters_responsible_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_shelters_created_by_users",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by"],
            ["users.id"],
            name="fk_shelters_verified_by_users",
        ),
    )
    op.create_index("ix_shelters_crisis_id", "shelters", ["crisis_id"])
    op.create_index("ix_shelters_status", "shelters", ["status"])
    op.create_index("ix_shelters_verified", "shelters", ["verified"])
    op.create_index("ix_shelters_shelter_type", "shelters", ["shelter_type"])
    op.create_index("geo_idx", "shelters", ["latitude", "longitude"])

    op.create_table(
        "beneficiaries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("vulnerability", vulnerability_type, nullable=True),
        sa.Column("notes", sa.TEXT(), nullable=True),
        sa.Column(
            "checked_in_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("checked_out_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name="fk_beneficiaries_shelter_id_shelters",
        ),
    )
    op.create_index("ix_beneficiaries_shelter_id", "beneficiaries", ["shelter_id"])
    op.create_index(
        "ix_beneficiaries_vulnerability",
        "beneficiaries",
        ["vulnerability"],
    )

    op.create_table(
        "resource_categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.VARCHAR(), nullable=False),
        sa.Column("unit", sa.VARCHAR(), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.UniqueConstraint("name", name="uq_resource_categories_name"),
    )

    op.create_table(
        "shelter_needs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity_needed", sa.Integer(), nullable=False),
        sa.Column(
            "priority",
            priority_level,
            nullable=False,
            server_default=sa.text("'medium'::priority_level"),
        ),
        sa.Column(
            "status",
            shelter_need_status,
            nullable=False,
            server_default=sa.text("'open'::shelter_need_status"),
        ),
        sa.Column(
            "declared_at",
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
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name="fk_shelter_needs_shelter_id_shelters",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["resource_categories.id"],
            name="fk_shelter_needs_category_id_resource_categories",
        ),
    )
    op.create_index("ix_shelter_needs_shelter_id", "shelter_needs", ["shelter_id"])
    op.create_index(
        "ix_shelter_needs_shelter_category_status",
        "shelter_needs",
        ["shelter_id", "category_id", "status"],
    )
    op.create_index("ix_shelter_needs_priority", "shelter_needs", ["priority"])

    op.create_table(
        "inventory_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "quantity_current",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["shelter_id"],
            ["shelters.id"],
            name="fk_inventory_items_shelter_id_shelters",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["resource_categories.id"],
            name="fk_inventory_items_category_id_resource_categories",
        ),
    )
    op.create_index(
        "one_snapshot_per_shelter_category",
        "inventory_items",
        ["shelter_id", "category_id"],
        unique=True,
    )

    op.create_table(
        "donations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("crisis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("donor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            donation_status,
            nullable=False,
            server_default=sa.text("'pledged'::donation_status"),
        ),
        sa.Column("note", sa.TEXT(), nullable=True),
        sa.Column(
            "pledged_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["crisis_id"],
            ["crises.id"],
            name="fk_donations_crisis_id_crises",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["resource_categories.id"],
            name="fk_donations_category_id_resource_categories",
        ),
        sa.ForeignKeyConstraint(
            ["donor_user_id"],
            ["users.id"],
            name="fk_donations_donor_user_id_users",
        ),
    )
    op.create_index("ix_donations_crisis_id", "donations", ["crisis_id"])
    op.create_index("ix_donations_status", "donations", ["status"])
    op.create_index("ix_donations_donor_user_id", "donations", ["donor_user_id"])

    op.create_table(
        "distributions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("donation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("origin_shelter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "destination_shelter_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transfer_type", transfer_type, nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            distribution_status,
            nullable=False,
            server_default=sa.text("'planned'::distribution_status"),
        ),
        sa.Column("dispatched_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["donation_id"],
            ["donations.id"],
            name="fk_distributions_donation_id_donations",
        ),
        sa.ForeignKeyConstraint(
            ["origin_shelter_id"],
            ["shelters.id"],
            name="fk_distributions_origin_shelter_id_shelters",
        ),
        sa.ForeignKeyConstraint(
            ["destination_shelter_id"],
            ["shelters.id"],
            name="fk_distributions_destination_shelter_id_shelters",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["resource_categories.id"],
            name="fk_distributions_category_id_resource_categories",
        ),
    )
    op.create_index("ix_distributions_donation_id", "distributions", ["donation_id"])
    op.create_index(
        "ix_distributions_origin_shelter_id",
        "distributions",
        ["origin_shelter_id"],
    )
    op.create_index(
        "ix_distributions_destination_shelter_id",
        "distributions",
        ["destination_shelter_id"],
    )
    op.create_index("ix_distributions_status", "distributions", ["status"])
    op.create_index(
        "ix_distributions_transfer_type",
        "distributions",
        ["transfer_type"],
    )

    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("message", sa.TEXT(), nullable=False),
        sa.Column(
            "read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_notifications_user_id_users",
        ),
    )
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.execute(
        "ALTER TABLE audit_log "
        "ALTER COLUMN action TYPE audit_action "
        "USING action::text::audit_action"
    )
    op.execute(
        "ALTER TABLE audit_log "
        "ALTER COLUMN entity_type TYPE audit_entity_type "
        "USING entity_type::text::audit_entity_type"
    )
    op.execute(
        "ALTER TABLE audit_log "
        "ADD CONSTRAINT fk_audit_log_author_id_users "
        "FOREIGN KEY (author_id) REFERENCES users (id) NOT VALID"
    )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_constraint(
        "fk_audit_log_author_id_users",
        "audit_log",
        type_="foreignkey",
    )
    op.execute(
        "ALTER TABLE audit_log "
        "ALTER COLUMN entity_type TYPE VARCHAR "
        "USING entity_type::text"
    )
    op.execute(
        "ALTER TABLE audit_log ALTER COLUMN action TYPE VARCHAR USING action::text"
    )

    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_distributions_transfer_type", table_name="distributions")
    op.drop_index("ix_distributions_status", table_name="distributions")
    op.drop_index(
        "ix_distributions_destination_shelter_id",
        table_name="distributions",
    )
    op.drop_index("ix_distributions_origin_shelter_id", table_name="distributions")
    op.drop_index("ix_distributions_donation_id", table_name="distributions")
    op.drop_table("distributions")

    op.drop_index("ix_donations_donor_user_id", table_name="donations")
    op.drop_index("ix_donations_status", table_name="donations")
    op.drop_index("ix_donations_crisis_id", table_name="donations")
    op.drop_table("donations")

    op.drop_index(
        "one_snapshot_per_shelter_category",
        table_name="inventory_items",
    )
    op.drop_table("inventory_items")

    op.drop_index("ix_shelter_needs_priority", table_name="shelter_needs")
    op.drop_index(
        "ix_shelter_needs_shelter_category_status",
        table_name="shelter_needs",
    )
    op.drop_index("ix_shelter_needs_shelter_id", table_name="shelter_needs")
    op.drop_table("shelter_needs")

    op.drop_table("resource_categories")

    op.drop_index("ix_beneficiaries_vulnerability", table_name="beneficiaries")
    op.drop_index("ix_beneficiaries_shelter_id", table_name="beneficiaries")
    op.drop_table("beneficiaries")

    op.drop_index("geo_idx", table_name="shelters")
    op.drop_index("ix_shelters_shelter_type", table_name="shelters")
    op.drop_index("ix_shelters_verified", table_name="shelters")
    op.drop_index("ix_shelters_status", table_name="shelters")
    op.drop_index("ix_shelters_crisis_id", table_name="shelters")
    op.drop_table("shelters")

    op.drop_constraint(
        "fk_crises_closed_by_users",
        "crises",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_crises_created_by_users",
        "crises",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_crises_organization_id_organizations",
        "crises",
        type_="foreignkey",
    )
    op.execute(
        "ALTER TABLE crises ALTER COLUMN state TYPE VARCHAR(2) USING state::text"
    )
    op.drop_column("crises", "organization_id")

    op.drop_table("users")
    op.drop_table("organizations")
    op.drop_table("roles")

    for enum_type in reversed(new_enums):
        enum_type.drop(bind, checkfirst=True)
