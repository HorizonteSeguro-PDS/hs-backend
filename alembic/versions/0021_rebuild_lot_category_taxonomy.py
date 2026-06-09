"""rebuild lot_category taxonomy

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-09

Substitui o enum `lot_category` por uma taxonomia mais detalhada combinada
com o front:

  Old (9 valores)             New (6 valores)
  food/water/bedding/        -> essenciais
  hygiene/clothing
  medicine                   -> saude
  animal                     -> animais
  money                      -> operacao
  other                      -> operacao  (fallback)

Mapeamento por NOME tem precedência (pra dividir 'hygiene' entre
ESSENCIAIS — kit_higiene — e INFANTIL_E_IDOSOS — fraldas/absorventes).

Também renomeia 5 categorias seedadas pra alinhar com a nova spec do front:
  alimento_nao_perecivel -> alimento
  kit_higiene_pessoal    -> kit_higiene
  fralda_descartavel     -> fralda_infantil
  kit_medico_basico      -> material_medico
  doacao_dinheiro        -> doacao_financeira

FKs em inventory_items/movements são por UUID — renomear `name` é seguro.
"""

import sqlalchemy as sa
from alembic import op


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


# (old_name, new_name, new_lot_category) — precedência sobre o mapeamento
# por enum (abaixo). Cobre as 11 categorias seedadas pelo seed.
_NAME_BUCKETS: list[tuple[str, str, str]] = [
    ("alimento_nao_perecivel", "alimento", "essenciais"),
    ("agua_potavel", "agua_potavel", "essenciais"),
    ("cobertor", "cobertor", "essenciais"),
    ("colchao", "colchao", "essenciais"),
    ("kit_higiene_pessoal", "kit_higiene", "essenciais"),
    ("kit_medico_basico", "material_medico", "saude"),
    ("fralda_descartavel", "fralda_infantil", "infantil_e_idosos"),
    ("fralda_geriatrica", "fralda_geriatrica", "infantil_e_idosos"),
    ("absorvente", "absorvente", "infantil_e_idosos"),
    ("racao_animal", "racao_animal", "animais"),
    ("doacao_dinheiro", "doacao_financeira", "operacao"),
]

# Fallback bucketing por valor antigo do enum (pra categorias custom
# criadas fora do seed).
_OLD_ENUM_BUCKETS: dict[str, str] = {
    "food": "essenciais",
    "water": "essenciais",
    "bedding": "essenciais",
    "hygiene": "essenciais",
    "clothing": "essenciais",
    "medicine": "saude",
    "animal": "animais",
    "money": "operacao",
    "other": "operacao",
}


def upgrade() -> None:
    op.drop_index(
        "ix_resource_categories_lot_category", table_name="resource_categories"
    )

    # 1) Converte coluna pra VARCHAR pra poder dropar o tipo enum
    op.execute(
        "ALTER TABLE resource_categories "
        "ALTER COLUMN lot_category TYPE VARCHAR USING lot_category::text"
    )

    # 2) Dropa tipo enum antigo
    op.execute("DROP TYPE lot_category")

    # 3) Cria tipo enum novo
    op.execute(
        "CREATE TYPE lot_category AS ENUM ("
        "'essenciais', 'saude', 'infantil_e_idosos', 'animais', "
        "'infraestrutura', 'operacao'"
        ")"
    )

    # 4) Rebucket + rename por NOME (precedência sobre fallback enum)
    for old_name, new_name, new_bucket in _NAME_BUCKETS:
        op.execute(
            sa.text(
                "UPDATE resource_categories "
                "SET name = :new_name, lot_category = :new_bucket "
                "WHERE name = :old_name"
            ).bindparams(
                old_name=old_name,
                new_name=new_name,
                new_bucket=new_bucket,
            )
        )

    # 5) Fallback por valor antigo do enum (pra categorias custom)
    for old_value, new_value in _OLD_ENUM_BUCKETS.items():
        op.execute(
            sa.text(
                "UPDATE resource_categories "
                "SET lot_category = :new_value "
                "WHERE lot_category = :old_value"
            ).bindparams(old_value=old_value, new_value=new_value)
        )

    # 6) Converte coluna de volta pro novo tipo enum
    op.execute(
        "ALTER TABLE resource_categories "
        "ALTER COLUMN lot_category TYPE lot_category "
        "USING lot_category::lot_category"
    )

    # 7) Recria índice
    op.create_index(
        "ix_resource_categories_lot_category",
        "resource_categories",
        ["lot_category"],
    )


def downgrade() -> None:
    """Downgrade é best-effort: nao recupera a granularidade antiga porque
    juntamos varios valores em essenciais/operacao. Mapeia de volta pros
    valores antigos mais proximos.
    """
    op.drop_index(
        "ix_resource_categories_lot_category", table_name="resource_categories"
    )

    op.execute(
        "ALTER TABLE resource_categories "
        "ALTER COLUMN lot_category TYPE VARCHAR USING lot_category::text"
    )
    op.execute("DROP TYPE lot_category")
    op.execute(
        "CREATE TYPE lot_category AS ENUM ("
        "'food', 'water', 'medicine', 'hygiene', 'bedding', "
        "'animal', 'money', 'clothing', 'other'"
        ")"
    )

    # Best-effort downgrade pra os valores antigos
    op.execute(
        "UPDATE resource_categories SET lot_category = 'other' "
        "WHERE lot_category = 'essenciais'"
    )
    op.execute(
        "UPDATE resource_categories SET lot_category = 'medicine' "
        "WHERE lot_category = 'saude'"
    )
    op.execute(
        "UPDATE resource_categories SET lot_category = 'hygiene' "
        "WHERE lot_category = 'infantil_e_idosos'"
    )
    op.execute(
        "UPDATE resource_categories SET lot_category = 'animal' "
        "WHERE lot_category = 'animais'"
    )
    op.execute(
        "UPDATE resource_categories SET lot_category = 'other' "
        "WHERE lot_category = 'infraestrutura'"
    )
    op.execute(
        "UPDATE resource_categories SET lot_category = 'other' "
        "WHERE lot_category = 'operacao'"
    )

    # Reverte os 5 renames de nome
    reverse_renames: list[tuple[str, str]] = [
        ("alimento", "alimento_nao_perecivel"),
        ("kit_higiene", "kit_higiene_pessoal"),
        ("material_medico", "kit_medico_basico"),
        ("fralda_infantil", "fralda_descartavel"),
        ("doacao_financeira", "doacao_dinheiro"),
    ]
    for new_name, old_name in reverse_renames:
        op.execute(
            sa.text(
                "UPDATE resource_categories SET name = :old_name WHERE name = :new_name"
            ).bindparams(new_name=new_name, old_name=old_name)
        )

    op.execute(
        "ALTER TABLE resource_categories "
        "ALTER COLUMN lot_category TYPE lot_category "
        "USING lot_category::lot_category"
    )
    op.create_index(
        "ix_resource_categories_lot_category",
        "resource_categories",
        ["lot_category"],
    )
