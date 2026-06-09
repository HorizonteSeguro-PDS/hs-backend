"""shelter manager dashboard — supply caps, lot category, transfer destination

Three structural changes that unblock GET /crises/{id}/operations:

1. `inventory_items.quantity_max` (nullable INT, > 0)
   Teto opcional do item naquele abrigo — usado pra derivar status
   Sufficient/Low/Critical na resposta.

2. `lot_category` enum + `resource_categories.lot_category`
   Taxonomia grossa em cima das 11 categorias (FOOD, WATER, MEDICINE,
   HYGIENE, BEDDING, ANIMAL, MONEY, CLOTHING, OTHER). Backfill pelas 11
   categorias seedadas; depois travado em NOT NULL.

3. `inventory_movements.destination_shelter_id` (UUID NULL, FK shelters)
   Identifica pra qual abrigo um TRANSFER_OUT foi. CHECK constraint amarra:
   só pode estar setado quando reason='transfer_out' AND direction='out'.

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


lot_category_enum = postgresql.ENUM(
    "food",
    "water",
    "medicine",
    "hygiene",
    "bedding",
    "animal",
    "money",
    "clothing",
    "other",
    name="lot_category",
    create_type=False,
)


# Mapeia as 11 categorias seedadas pra um bucket de lot_category. Se rodar a
# migration num banco onde alguem ja adicionou categoria nova, a UPDATE com
# fallback `else 'other'` garante que ela vira `other`.
_SEEDED_CATEGORY_BUCKETS: list[tuple[str, str]] = [
    ("agua_potavel", "water"),
    ("cobertor", "bedding"),
    ("colchao", "bedding"),
    ("kit_medico_basico", "medicine"),
    ("kit_higiene_pessoal", "hygiene"),
    ("fralda_descartavel", "hygiene"),
    ("fralda_geriatrica", "hygiene"),
    ("absorvente", "hygiene"),
    ("alimento_nao_perecivel", "food"),
    ("racao_animal", "animal"),
    ("doacao_dinheiro", "money"),
]


def upgrade() -> None:
    # ----------------------------------------------------------------------- #
    # 1) inventory_items.quantity_max                                         #
    # ----------------------------------------------------------------------- #
    op.add_column(
        "inventory_items",
        sa.Column("quantity_max", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_inventory_items_quantity_max_positive",
        "inventory_items",
        "(quantity_max IS NULL OR quantity_max > 0)",
    )

    # ----------------------------------------------------------------------- #
    # 2) lot_category enum + resource_categories.lot_category                 #
    # ----------------------------------------------------------------------- #
    lot_category_enum.create(op.get_bind(), checkfirst=True)

    # Adiciona nullable primeiro, pra dar tempo de backfillar.
    op.add_column(
        "resource_categories",
        sa.Column("lot_category", lot_category_enum, nullable=True),
    )

    # Backfill pelas 11 categorias conhecidas.
    for name, bucket in _SEEDED_CATEGORY_BUCKETS:
        op.execute(
            sa.text(
                "UPDATE resource_categories SET lot_category = :bucket "
                "WHERE name = :name"
            ).bindparams(bucket=bucket, name=name)
        )

    # Fallback pra qualquer categoria que tenha sido inserida fora do seed.
    op.execute(
        "UPDATE resource_categories SET lot_category = 'other' "
        "WHERE lot_category IS NULL"
    )

    # Trava NOT NULL agora que toda linha foi backfillada.
    op.alter_column("resource_categories", "lot_category", nullable=False)

    op.create_index(
        "ix_resource_categories_lot_category",
        "resource_categories",
        ["lot_category"],
    )

    # ----------------------------------------------------------------------- #
    # 3) inventory_movements.destination_shelter_id + CHECK                   #
    # ----------------------------------------------------------------------- #
    op.add_column(
        "inventory_movements",
        sa.Column(
            "destination_shelter_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_inventory_movements_destination_shelter_id_shelters",
        "inventory_movements",
        "shelters",
        ["destination_shelter_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    # CHECK: só pode setar destination_shelter_id em TRANSFER_OUT.
    op.create_check_constraint(
        "ck_inventory_movements_destination_only_on_transfer_out",
        "inventory_movements",
        "("
        "(direction = 'out' AND reason = 'transfer_out' "
        " AND destination_shelter_id IS NOT NULL)"
        " OR ("
        "  (direction <> 'out' OR reason <> 'transfer_out') "
        "  AND destination_shelter_id IS NULL"
        " )"
        ")",
    )
    op.create_index(
        "ix_inventory_movements_destination_shelter_id",
        "inventory_movements",
        ["destination_shelter_id"],
    )


def downgrade() -> None:
    # 3) destination_shelter_id
    op.drop_index(
        "ix_inventory_movements_destination_shelter_id",
        table_name="inventory_movements",
    )
    op.drop_constraint(
        "ck_inventory_movements_destination_only_on_transfer_out",
        "inventory_movements",
        type_="check",
    )
    op.drop_constraint(
        "fk_inventory_movements_destination_shelter_id_shelters",
        "inventory_movements",
        type_="foreignkey",
    )
    op.drop_column("inventory_movements", "destination_shelter_id")

    # 2) lot_category
    op.drop_index(
        "ix_resource_categories_lot_category",
        table_name="resource_categories",
    )
    op.drop_column("resource_categories", "lot_category")
    lot_category_enum.drop(op.get_bind(), checkfirst=True)

    # 1) quantity_max
    op.drop_constraint(
        "ck_inventory_items_quantity_max_positive",
        "inventory_items",
        type_="check",
    )
    op.drop_column("inventory_items", "quantity_max")
