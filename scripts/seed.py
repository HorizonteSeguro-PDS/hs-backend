"""Dev database seeder. Run after `alembic upgrade head`.

Usage:
    python scripts/seed.py
    python scripts/seed.py --reset   # delete seeded rows first

Creates:
  - 1 demo organization (Horizonte Seguro - Demo)
  - 4 users (dev / crisis_manager / shelter_manager / multi-role tester);
    todos exceto o dev ficam vinculados a essa org.
  - 8 sample crises (3 das quais com shelters linkados)
  - 4 sample shelters, todos sob a demo org. Um deles (`Ginásio
    Poliesportivo Municipal`) tem id fixo `DEMO_FULL_SHELTER_ID` e é o
    abrigo "rico" usado pela feature de planilha.
  - users_shelters: 2 shelter_managers por abrigo (active_managers=2)
  - 11 resource_categories (com lot_category)
  - inventory_items por abrigo (com quantity_max definido) + reforço de
    estoque no DEMO_FULL_SHELTER via record_movement (pra cobrir categorias
    nao listadas no INVENTORY_ITEMS_SPEC do Ginásio).
  - inventory_movements: histórico de doações, distribuições e
    transferências entre abrigos.
  - beneficiaries com shelter_stays abertos pra popular a tela "Pessoas"
    (5 pessoas por abrigo — as do Ginásio aparecem primeiro pra que o
    spreadsheet feature ache BENEFICIARIES_SPEC[0] no demo shelter).

Sheltered people are NOT modelled as USERs — they live in the BENEFICIARY
entity.

Idempotent: re-running skips rows que já existem (matched by email/name/cpf).
Use --reset pra wipar tudo antes.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select, text  # noqa: E402

from domain.auth.enums import Role  # noqa: E402
from domain.crisis.enums import CrisisStatus, CrisisType  # noqa: E402
from domain.inventory.schemas import InventoryMovementCreateRequest  # noqa: E402
from domain.models.audit_log import AuditLog  # noqa: E402, F401 — registers metadata
from domain.models.beneficiary import Beneficiary  # noqa: E402
from domain.models.crises_shelters import CrisesShelters  # noqa: E402
from domain.models.crisis import Crisis  # noqa: E402
from domain.models.inventory_item import InventoryItem  # noqa: E402
from domain.models.inventory_movement import InventoryMovement  # noqa: E402
from domain.models.resource_category import ResourceCategory  # noqa: E402
from domain.models.shelter import Shelter  # noqa: E402
from domain.models.shelter_stay import ShelterStay  # noqa: E402
from domain.models.user import User  # noqa: E402
from domain.models.user_role import UserRole  # noqa: E402
from domain.models.users_crises import UsersCrises  # noqa: E402
from domain.models.users_shelters import UsersShelters  # noqa: E402
from domain.schemas.enums import (  # noqa: E402
    LotCategory,
    MovementDirection,
    MovementReason,
    OrganizationType,
    ResourceUnit,
    ShelterStatus,
    ShelterType,
    VulnerabilityType,
)
from services.auth_service import (  # noqa: E402
    create_access_token,
    grant_role,
    hash_password,
)
from services.inventory_service import InventoryService  # noqa: E402
from utils.database import SessionLocal  # noqa: E402

DEFAULT_PASSWORD = "admin1234"

# -------------------------------------------------------------------------- #
# Organization                                                               #
# -------------------------------------------------------------------------- #

ORGANIZATION_NAME = "Horizonte Seguro - Demo"
ORGANIZATION_TYPE = OrganizationType.MIXED

# -------------------------------------------------------------------------- #
# Demo "full" shelter — usado pela feature de planilha. ID é fixo pra que    #
# o front consiga apontar pra ele sem precisar consultar a API.              #
# -------------------------------------------------------------------------- #

DEMO_FULL_SHELTER_ID = UUID("7d70e036-99d7-4aeb-9ed8-1a81aaca43d0")
DEMO_FULL_SHELTER_NAME = "Ginásio Poliesportivo Municipal"

# -------------------------------------------------------------------------- #
# Users                                                                      #
# -------------------------------------------------------------------------- #

USERS_SPEC: list[dict] = [
    {
        "email": "admin@horizonteseguro.app",
        "name": "Admin Dev",
        "roles": [Role.DEV],
        "assign_to_org": False,  # dev é global, sem org
    },
    {
        "email": "gestor.crise@horizonteseguro.app",
        "name": "Gestor de Crise",
        "roles": [Role.CRISIS_MANAGER],
        "assign_to_org": True,
    },
    {
        "email": "gestor.abrigo@horizonteseguro.app",
        "name": "Gestor de Abrigo",
        "roles": [Role.SHELTER_MANAGER],
        "assign_to_org": True,
    },
    {
        "email": "multi@horizonteseguro.app",
        "name": "Multi-role Tester",
        "roles": [Role.CRISIS_MANAGER, Role.SHELTER_MANAGER],
        "assign_to_org": True,
    },
]

# Emails que foram seedados em iterações anteriores e que não fazem mais parte
# do USERS_SPEC. O --reset apaga essas linhas pra não deixarem órfãs no banco.
LEGACY_USER_EMAILS = ["abrigado@horizonteseguro.app"]

# Severity na escala nova 0-3:
#   0 = INATIVO, 1 = BAIXA, 2 = MÉDIA, 3 = ALTA
CRISES_SPEC = [
    {
        "name": "Enchente no Vale do Taquari",
        "type": CrisisType.FLOOD,
        "state": "RS",
        "city": "Lajeado",
        "latitude": -29.4669,
        "longitude": -51.9614,
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Enchente em Maceió",
        "type": CrisisType.FLOOD,
        "description": "Alagamentos em bairros ribeirinhos e necessidade de acolhimento emergencial.",
        "state": "AL",
        "city": "Maceió",
        "latitude": -9.6499,
        "longitude": -35.7089,
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Deslizamento no Recife",
        "type": CrisisType.LANDSLIDE,
        "description": "Deslizamento em área de encosta com famílias desalojadas.",
        "state": "PE",
        "city": "Recife",
        "latitude": -8.0476,
        "longitude": -34.8770,
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Estiagem Prolongada em Fortaleza",
        "type": CrisisType.OTHER,
        "description": "Seca/estiagem prolongada com restrição de abastecimento em comunidades vulneráveis.",
        "state": "CE",
        "city": "Fortaleza",
        "latitude": -3.7319,
        "longitude": -38.5267,
        "severity_initial": 2,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Incêndio Florestal Chapada",
        "type": CrisisType.FIRE,
        "state": "BA",
        "city": "Palmeiras",
        "latitude": -12.5106,
        "longitude": -41.5764,
        "severity_initial": 2,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Deslizamento Serra Gaúcha",
        "type": CrisisType.LANDSLIDE,
        "state": "RS",
        "city": "Gramado",
        "latitude": -29.3788,
        "longitude": -50.8740,
        "severity_initial": 3,
        "status": CrisisStatus.CLOSED,
        "close_reason": "Área estabilizada e famílias reassentadas.",
    },
    {
        "name": "Evento Atípico Nordeste",
        "type": CrisisType.OTHER,
        "state": "CE",
        "city": "Fortaleza",
        "latitude": -3.7319,
        "longitude": -38.5267,
        "severity_initial": 1,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Enchente Zona Leste SP",
        "type": CrisisType.FLOOD,
        "state": "SP",
        "city": "São Paulo",
        "latitude": -23.5505,
        "longitude": -46.6333,
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
]

SHELTERS_SPEC = [
    {
        "name": "Abrigo Comunitário Benedito Bentes",
        "address": "Rua da Esperança, 120",
        "neighborhood": "Benedito Bentes",
        "city": "Maceió",
        "state": "AL",
        "cep": "57084-000",
        "latitude": -9.5568,
        "longitude": -35.7327,
        "capacity": 80,
        "occupation": 32,
        "shelter_type": ShelterType.COMMUNITY_HOME,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    },
    {
        "name": "Escola Municipal Esperança",
        "address": "Avenida Principal, 450",
        "neighborhood": "Tabuleiro do Martins",
        "city": "Maceió",
        "state": "AL",
        "cep": "57081-100",
        "latitude": -9.5901,
        "longitude": -35.7585,
        "capacity": 150,
        "occupation": 74,
        "shelter_type": ShelterType.IMPROVISED_PUBLIC,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    },
    {
        # id fixo: a feature de planilha aponta pra este abrigo pelo UUID
        # constante (DEMO_FULL_SHELTER_ID) e nao depende do nome.
        "id": DEMO_FULL_SHELTER_ID,
        "name": DEMO_FULL_SHELTER_NAME,
        "address": "Rua do Esporte, 88",
        "neighborhood": "Centro",
        "city": "Salvador",
        "state": "BA",
        "cep": "40015-000",
        "latitude": -12.9714,
        "longitude": -38.5014,
        "capacity": 220,
        "occupation": 118,
        "shelter_type": ShelterType.IMPROVISED_PUBLIC,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    },
    {
        "name": "Centro de Apoio Humanitário Nordeste",
        "address": "Avenida Recife Solidário, 1000",
        "neighborhood": "Imbiribeira",
        "city": "Recife",
        "state": "PE",
        "cep": "51170-000",
        "latitude": -8.1087,
        "longitude": -34.9093,
        "capacity": 120,
        "occupation": 45,
        "shelter_type": ShelterType.INSTITUTIONAL,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    },
]

CRISIS_SHELTER_LINKS = {
    "Enchente em Maceió": [
        "Abrigo Comunitário Benedito Bentes",
        "Escola Municipal Esperança",
    ],
    "Deslizamento no Recife": [
        "Centro de Apoio Humanitário Nordeste",
    ],
    "Incêndio Florestal Chapada": [
        DEMO_FULL_SHELTER_NAME,
        "Centro de Apoio Humanitário Nordeste",
    ],
}

# (name, unit, lot_category, description)
CATEGORIES_SPEC: list[tuple[str, ResourceUnit, LotCategory, str]] = [
    ("agua_potavel", ResourceUnit.L, LotCategory.WATER, "Água potável engarrafada"),
    ("cobertor", ResourceUnit.UNIDADE, LotCategory.BEDDING, "Cobertor adulto"),
    ("colchao", ResourceUnit.UNIDADE, LotCategory.BEDDING, "Colchão de campanha"),
    (
        "kit_medico_basico",
        ResourceUnit.UNIDADE,
        LotCategory.MEDICINE,
        "Curativo, antitérmico, soro fisiológico",
    ),
    (
        "kit_higiene_pessoal",
        ResourceUnit.UNIDADE,
        LotCategory.HYGIENE,
        "Escova, pasta, sabonete, toalha",
    ),
    (
        "fralda_descartavel",
        ResourceUnit.UNIDADE,
        LotCategory.HYGIENE,
        "Bebê — pacote",
    ),
    (
        "fralda_geriatrica",
        ResourceUnit.UNIDADE,
        LotCategory.HYGIENE,
        "Adulto — pacote",
    ),
    ("absorvente", ResourceUnit.UNIDADE, LotCategory.HYGIENE, "Pacote padrão"),
    (
        "alimento_nao_perecivel",
        ResourceUnit.KG,
        LotCategory.FOOD,
        "Arroz, feijão, açúcar, óleo, etc.",
    ),
    ("racao_animal", ResourceUnit.KG, LotCategory.ANIMAL, "Ração para cães e gatos"),
    (
        "doacao_dinheiro",
        ResourceUnit.REAL,
        LotCategory.MONEY,
        "Doação em dinheiro pra logística",
    ),
]

# -------------------------------------------------------------------------- #
# Inventory items por abrigo (snapshot direto, sem record_movement)          #
# Mistura status (Sufficient/Low/Critical) pro dashboard ficar variado.      #
# -------------------------------------------------------------------------- #
# (shelter_name, category_name, quantity_current, quantity_max)
INVENTORY_ITEMS_SPEC: list[tuple[str, str, int, int | None]] = [
    # Benedito Bentes — escassez geral
    ("Abrigo Comunitário Benedito Bentes", "alimento_nao_perecivel", 300, 1000),
    ("Abrigo Comunitário Benedito Bentes", "agua_potavel", 200, 500),
    ("Abrigo Comunitário Benedito Bentes", "cobertor", 40, 80),
    ("Abrigo Comunitário Benedito Bentes", "kit_higiene_pessoal", 15, 80),
    ("Abrigo Comunitário Benedito Bentes", "kit_medico_basico", 20, 30),
    # Escola Esperança — melhor situacao
    ("Escola Municipal Esperança", "alimento_nao_perecivel", 800, 1500),
    ("Escola Municipal Esperança", "agua_potavel", 350, 1000),
    ("Escola Municipal Esperança", "cobertor", 60, 100),
    ("Escola Municipal Esperança", "colchao", 40, 80),
    ("Escola Municipal Esperança", "kit_medico_basico", 5, 30),
    # Ginásio Salvador (DEMO_FULL_SHELTER) — agua critica + 4 categorias seedadas
    # AQUI. As outras 7 entram via seed_demo_full_shelter / record_movement.
    (DEMO_FULL_SHELTER_NAME, "alimento_nao_perecivel", 600, 2000),
    (DEMO_FULL_SHELTER_NAME, "agua_potavel", 100, 1500),
    (DEMO_FULL_SHELTER_NAME, "colchao", 80, 150),
    (DEMO_FULL_SHELTER_NAME, "fralda_descartavel", 30, 100),
    # Centro Humanitário Recife — equilibrado
    ("Centro de Apoio Humanitário Nordeste", "alimento_nao_perecivel", 400, 1000),
    ("Centro de Apoio Humanitário Nordeste", "agua_potavel", 350, 600),
    ("Centro de Apoio Humanitário Nordeste", "kit_medico_basico", 25, 40),
    ("Centro de Apoio Humanitário Nordeste", "kit_higiene_pessoal", 50, 100),
]

# -------------------------------------------------------------------------- #
# Inventory movements (historico)                                            #
# -------------------------------------------------------------------------- #
# (shelter_name, category_name, direction, quantity, reason, source,
#  destination_shelter_name)
INVENTORY_MOVEMENTS_SPEC: list[
    tuple[
        str,
        str,
        MovementDirection,
        int,
        MovementReason,
        str | None,
        str | None,
    ]
] = [
    # Benedito Bentes
    (
        "Abrigo Comunitário Benedito Bentes",
        "alimento_nao_perecivel",
        MovementDirection.IN,
        100,
        MovementReason.DONATION,
        "Igreja Local",
        None,
    ),
    (
        "Abrigo Comunitário Benedito Bentes",
        "agua_potavel",
        MovementDirection.IN,
        200,
        MovementReason.DONATION,
        "Cruz Vermelha",
        None,
    ),
    (
        "Abrigo Comunitário Benedito Bentes",
        "alimento_nao_perecivel",
        MovementDirection.OUT,
        30,
        MovementReason.DISTRIBUTION,
        None,
        None,
    ),
    (
        "Abrigo Comunitário Benedito Bentes",
        "kit_higiene_pessoal",
        MovementDirection.OUT,
        20,
        MovementReason.DISTRIBUTION,
        None,
        None,
    ),
    (
        "Abrigo Comunitário Benedito Bentes",
        "cobertor",
        MovementDirection.OUT,
        10,
        MovementReason.TRANSFER_OUT,
        None,
        "Escola Municipal Esperança",
    ),
    # Escola Esperança
    (
        "Escola Municipal Esperança",
        "alimento_nao_perecivel",
        MovementDirection.IN,
        200,
        MovementReason.DONATION,
        "Mercado Solidário",
        None,
    ),
    (
        "Escola Municipal Esperança",
        "cobertor",
        MovementDirection.IN,
        10,
        MovementReason.TRANSFER_IN,
        "Abrigo Comunitário Benedito Bentes",
        None,
    ),
    (
        "Escola Municipal Esperança",
        "agua_potavel",
        MovementDirection.IN,
        300,
        MovementReason.DONATION,
        "ONG SOS Vidas",
        None,
    ),
    (
        "Escola Municipal Esperança",
        "alimento_nao_perecivel",
        MovementDirection.OUT,
        50,
        MovementReason.DISTRIBUTION,
        None,
        None,
    ),
    # Ginásio Salvador
    (
        DEMO_FULL_SHELTER_NAME,
        "alimento_nao_perecivel",
        MovementDirection.IN,
        500,
        MovementReason.DONATION,
        "Doação Empresarial",
        None,
    ),
    (
        DEMO_FULL_SHELTER_NAME,
        "agua_potavel",
        MovementDirection.IN,
        200,
        MovementReason.DONATION,
        "Defesa Civil",
        None,
    ),
    (
        DEMO_FULL_SHELTER_NAME,
        "fralda_descartavel",
        MovementDirection.OUT,
        50,
        MovementReason.DISTRIBUTION,
        None,
        None,
    ),
    (
        DEMO_FULL_SHELTER_NAME,
        "colchao",
        MovementDirection.OUT,
        5,
        MovementReason.TRANSFER_OUT,
        None,
        "Centro de Apoio Humanitário Nordeste",
    ),
    # Centro Humanitário Recife
    (
        "Centro de Apoio Humanitário Nordeste",
        "alimento_nao_perecivel",
        MovementDirection.IN,
        200,
        MovementReason.DONATION,
        "Banco de Alimentos",
        None,
    ),
    (
        "Centro de Apoio Humanitário Nordeste",
        "agua_potavel",
        MovementDirection.IN,
        100,
        MovementReason.DONATION,
        "Cruz Vermelha",
        None,
    ),
    (
        "Centro de Apoio Humanitário Nordeste",
        "colchao",
        MovementDirection.IN,
        5,
        MovementReason.TRANSFER_IN,
        DEMO_FULL_SHELTER_NAME,
        None,
    ),
    (
        "Centro de Apoio Humanitário Nordeste",
        "kit_higiene_pessoal",
        MovementDirection.OUT,
        30,
        MovementReason.DISTRIBUTION,
        None,
        None,
    ),
]

# -------------------------------------------------------------------------- #
# DEMO_FULL_SHELTER — reforço de estoque pra todas as 11 categorias          #
# -------------------------------------------------------------------------- #
# Aplicado via record_movement (donation). Itens já presentes em
# INVENTORY_ITEMS_SPEC pra este abrigo sao pulados (seed_demo_full_shelter
# checa existencia primeiro). Garante que a planilha de demo cubra tudo.
DEMO_FULL_SHELTER_INVENTORY: dict[str, int] = {
    "agua_potavel": 1800,
    "cobertor": 260,
    "colchao": 140,
    "kit_medico_basico": 45,
    "kit_higiene_pessoal": 180,
    "fralda_descartavel": 70,
    "fralda_geriatrica": 38,
    "absorvente": 95,
    "alimento_nao_perecivel": 920,
    "racao_animal": 160,
    "doacao_dinheiro": 12500,
}

# -------------------------------------------------------------------------- #
# Beneficiaries (com stays abertos)                                          #
# -------------------------------------------------------------------------- #
# DICT format pra interoperar com a feature de planilha (que faz spec["cpf"]
# etc). As primeiras entries pertencem ao DEMO_FULL_SHELTER_NAME pra que
# `BENEFICIARIES_SPEC[0]` sirva o spreadsheet test.
BENEFICIARIES_SPEC: list[dict] = [
    # === DEMO_FULL_SHELTER (Ginásio Poliesportivo Municipal) ===
    {
        "shelter_name": DEMO_FULL_SHELTER_NAME,
        "cpf": "333.444.555-01",
        "name": "Mariana Pinto",
        "age": 25,
        "vulnerability": VulnerabilityType.PREGNANT,
        "notes": "Gestante; acompanhamento semanal solicitado.",
    },
    {
        "shelter_name": DEMO_FULL_SHELTER_NAME,
        "cpf": "333.444.555-02",
        "name": "José Ferreira",
        "age": 75,
        "vulnerability": VulnerabilityType.ELDERLY,
        "notes": "Usa medicação contínua; priorizar acesso ao posto médico.",
    },
    {
        "shelter_name": DEMO_FULL_SHELTER_NAME,
        "cpf": "333.444.555-03",
        "name": "Camila Rodrigues",
        "age": 9,
        "vulnerability": VulnerabilityType.CHILD,
        "notes": "Criança acompanhada pela responsável Maria Almeida.",
    },
    {
        "shelter_name": DEMO_FULL_SHELTER_NAME,
        "cpf": "333.444.555-04",
        "name": "Roberto Silva",
        "age": 50,
        "vulnerability": VulnerabilityType.NONE,
        "notes": None,
    },
    {
        "shelter_name": DEMO_FULL_SHELTER_NAME,
        "cpf": "333.444.555-05",
        "name": "Patrícia Lima",
        "age": 35,
        "vulnerability": VulnerabilityType.CHRONIC_ILLNESS,
        "notes": "Hipertensão; medicação contínua.",
    },
    # === Benedito Bentes ===
    {
        "shelter_name": "Abrigo Comunitário Benedito Bentes",
        "cpf": "111.222.333-01",
        "name": "João da Silva",
        "age": 8,
        "vulnerability": VulnerabilityType.CHILD,
        "notes": None,
    },
    {
        "shelter_name": "Abrigo Comunitário Benedito Bentes",
        "cpf": "111.222.333-02",
        "name": "Maria Souza",
        "age": 67,
        "vulnerability": VulnerabilityType.ELDERLY,
        "notes": None,
    },
    {
        "shelter_name": "Abrigo Comunitário Benedito Bentes",
        "cpf": "111.222.333-03",
        "name": "Ana Pereira",
        "age": 28,
        "vulnerability": VulnerabilityType.PREGNANT,
        "notes": None,
    },
    {
        "shelter_name": "Abrigo Comunitário Benedito Bentes",
        "cpf": "111.222.333-04",
        "name": "Carlos Oliveira",
        "age": 45,
        "vulnerability": VulnerabilityType.DISABLED,
        "notes": "Pessoa com mobilidade reduzida; acomodado próximo à saída.",
    },
    {
        "shelter_name": "Abrigo Comunitário Benedito Bentes",
        "cpf": "111.222.333-05",
        "name": "Beatriz Santos",
        "age": 12,
        "vulnerability": VulnerabilityType.CHILD,
        "notes": None,
    },
    # === Escola Esperança ===
    {
        "shelter_name": "Escola Municipal Esperança",
        "cpf": "222.333.444-01",
        "name": "Pedro Lima",
        "age": 70,
        "vulnerability": VulnerabilityType.ELDERLY,
        "notes": None,
    },
    {
        "shelter_name": "Escola Municipal Esperança",
        "cpf": "222.333.444-02",
        "name": "Lúcia Mendes",
        "age": 32,
        "vulnerability": VulnerabilityType.NONE,
        "notes": None,
    },
    {
        "shelter_name": "Escola Municipal Esperança",
        "cpf": "222.333.444-03",
        "name": "Tiago Almeida",
        "age": 6,
        "vulnerability": VulnerabilityType.CHILD,
        "notes": None,
    },
    {
        "shelter_name": "Escola Municipal Esperança",
        "cpf": "222.333.444-04",
        "name": "Rosa Carvalho",
        "age": 58,
        "vulnerability": VulnerabilityType.CHRONIC_ILLNESS,
        "notes": None,
    },
    {
        "shelter_name": "Escola Municipal Esperança",
        "cpf": "222.333.444-05",
        "name": "Fernando Costa",
        "age": 40,
        "vulnerability": VulnerabilityType.DISABLED,
        "notes": None,
    },
    # === Centro Humanitário Recife ===
    {
        "shelter_name": "Centro de Apoio Humanitário Nordeste",
        "cpf": "444.555.666-01",
        "name": "Antônio Pereira",
        "age": 60,
        "vulnerability": VulnerabilityType.ELDERLY,
        "notes": None,
    },
    {
        "shelter_name": "Centro de Apoio Humanitário Nordeste",
        "cpf": "444.555.666-02",
        "name": "Juliana Costa",
        "age": 30,
        "vulnerability": VulnerabilityType.NONE,
        "notes": None,
    },
    {
        "shelter_name": "Centro de Apoio Humanitário Nordeste",
        "cpf": "444.555.666-03",
        "name": "Felipe Santos",
        "age": 11,
        "vulnerability": VulnerabilityType.CHILD,
        "notes": None,
    },
    {
        "shelter_name": "Centro de Apoio Humanitário Nordeste",
        "cpf": "444.555.666-04",
        "name": "Sandra Lima",
        "age": 65,
        "vulnerability": VulnerabilityType.ELDERLY,
        "notes": None,
    },
    {
        "shelter_name": "Centro de Apoio Humanitário Nordeste",
        "cpf": "444.555.666-05",
        "name": "Diego Mendes",
        "age": 22,
        "vulnerability": VulnerabilityType.DISABLED,
        "notes": None,
    },
]

# Quais users (por email) viram managers de cada abrigo. 2 managers por abrigo
# pra deixar active_managers != 0 na resposta.
SHELTER_MANAGER_ASSIGNMENTS: dict[str, list[str]] = {
    "Abrigo Comunitário Benedito Bentes": [
        "gestor.abrigo@horizonteseguro.app",
        "multi@horizonteseguro.app",
    ],
    "Escola Municipal Esperança": [
        "gestor.abrigo@horizonteseguro.app",
        "multi@horizonteseguro.app",
    ],
    DEMO_FULL_SHELTER_NAME: [
        "gestor.abrigo@horizonteseguro.app",
        "multi@horizonteseguro.app",
    ],
    "Centro de Apoio Humanitário Nordeste": [
        "gestor.abrigo@horizonteseguro.app",
        "multi@horizonteseguro.app",
    ],
}


SEEDED_USER_EMAILS = [u["email"] for u in USERS_SPEC]
SEEDED_CRISIS_NAMES = [c["name"] for c in CRISES_SPEC]
SEEDED_SHELTER_NAMES = [s["name"] for s in SHELTERS_SPEC]
SEEDED_CATEGORY_NAMES = [name for name, _, _, _ in CATEGORIES_SPEC]
SEEDED_BENEFICIARY_CPFS = [spec["cpf"] for spec in BENEFICIARIES_SPEC]


# -------------------------------------------------------------------------- #
# Reset                                                                      #
# -------------------------------------------------------------------------- #


def reset(session) -> None:
    """Wipe rows previously inserted by this seeder. Safe to run repeatedly."""
    seeded_user_rows = session.scalars(
        select(User).where(User.email.in_(SEEDED_USER_EMAILS + LEGACY_USER_EMAILS))
    ).all()
    seeded_user_ids = [u.id for u in seeded_user_rows]
    seeded_crisis_rows = session.scalars(
        select(Crisis).where(Crisis.name.in_(SEEDED_CRISIS_NAMES))
    ).all()
    seeded_crisis_ids = [c.id for c in seeded_crisis_rows]
    seeded_shelter_rows = session.scalars(
        select(Shelter).where(Shelter.name.in_(SEEDED_SHELTER_NAMES))
    ).all()
    seeded_shelter_ids = [s.id for s in seeded_shelter_rows]
    seeded_beneficiary_rows = session.scalars(
        select(Beneficiary).where(Beneficiary.cpf.in_(SEEDED_BENEFICIARY_CPFS))
    ).all()
    seeded_beneficiary_ids = [b.id for b in seeded_beneficiary_rows]

    # --- Order matters: filhos primeiro pra nao bater em FK constraints --- #

    # inventory_movements depende de shelters, categories e users.
    if seeded_shelter_ids:
        session.execute(
            delete(InventoryMovement).where(
                InventoryMovement.shelter_id.in_(seeded_shelter_ids)
            )
        )
        session.execute(
            delete(InventoryMovement).where(
                InventoryMovement.destination_shelter_id.in_(seeded_shelter_ids)
            )
        )
        # inventory_items.
        session.execute(
            delete(InventoryItem).where(
                InventoryItem.shelter_id.in_(seeded_shelter_ids)
            )
        )
        # shelter_stays (por shelter — apaga até stays abertos de beneficiarios
        # nao seedados que por acaso estavam num shelter seedado).
        session.execute(
            delete(ShelterStay).where(ShelterStay.shelter_id.in_(seeded_shelter_ids))
        )
        # users_shelters
        session.execute(
            delete(UsersShelters).where(
                UsersShelters.shelter_id.in_(seeded_shelter_ids)
            )
        )

    # beneficiaries — depois de shelter_stays.
    if seeded_beneficiary_ids:
        session.execute(
            delete(ShelterStay).where(
                ShelterStay.beneficiary_id.in_(seeded_beneficiary_ids)
            )
        )
        session.execute(
            delete(Beneficiary).where(Beneficiary.id.in_(seeded_beneficiary_ids))
        )

    if seeded_crisis_ids:
        session.execute(
            delete(CrisesShelters).where(
                CrisesShelters.crisis_id.in_(seeded_crisis_ids)
            )
        )
        session.execute(
            delete(UsersCrises).where(UsersCrises.crisis_id.in_(seeded_crisis_ids))
        )
    if seeded_shelter_ids:
        session.execute(
            delete(CrisesShelters).where(
                CrisesShelters.shelter_id.in_(seeded_shelter_ids)
            )
        )
        session.execute(delete(Shelter).where(Shelter.id.in_(seeded_shelter_ids)))
    if seeded_crisis_ids:
        session.execute(delete(Crisis).where(Crisis.id.in_(seeded_crisis_ids)))
    if seeded_user_ids:
        session.execute(
            delete(UsersCrises).where(UsersCrises.user_id.in_(seeded_user_ids))
        )
        session.execute(
            delete(UsersShelters).where(UsersShelters.user_id.in_(seeded_user_ids))
        )
        session.execute(delete(UserRole).where(UserRole.user_id.in_(seeded_user_ids)))
        session.execute(delete(User).where(User.id.in_(seeded_user_ids)))

    # Resource categories sao compartilhadas; apaga so as seedadas.
    session.execute(
        delete(ResourceCategory).where(ResourceCategory.name.in_(SEEDED_CATEGORY_NAMES))
    )

    # Organization demo — nao tem model, apaga via SQL.
    session.execute(
        text("DELETE FROM organizations WHERE name = :name"),
        {"name": ORGANIZATION_NAME},
    )

    session.commit()
    print(
        "[seed] reset: deleted seeded users, crises, shelters, inventory, "
        "beneficiaries, organization, categories."
    )


# -------------------------------------------------------------------------- #
# Helpers de seed                                                            #
# -------------------------------------------------------------------------- #


def seed_organization(session) -> UUID:
    """Get-or-create the demo organization. Returns its id."""
    row = session.execute(
        text("SELECT id FROM organizations WHERE name = :name"),
        {"name": ORGANIZATION_NAME},
    ).first()
    if row is not None:
        print(f"[seed] organization {ORGANIZATION_NAME!r} already exists.")
        return row[0]

    org_id = uuid4()
    session.execute(
        text(
            "INSERT INTO organizations (id, name, type, contact_email) "
            "VALUES (:id, :name, CAST(:type AS organization_type), :email)"
        ),
        {
            "id": org_id,
            "name": ORGANIZATION_NAME,
            "type": ORGANIZATION_TYPE.value,
            "email": "contato@horizonteseguro.app",
        },
    )
    print(f"[seed] created organization {ORGANIZATION_NAME!r}.")
    return org_id


def seed_users(session, *, organization_id: UUID) -> dict[str, tuple[User, list[Role]]]:
    """Get-or-create seed users keyed by email. Returns {email: (user, roles)}."""
    out: dict[str, tuple[User, list[Role]]] = {}
    for spec in USERS_SPEC:
        desired_org_id = organization_id if spec["assign_to_org"] else None
        existing = session.scalar(select(User).where(User.email == spec["email"]))
        if existing is not None:
            print(f"[seed] user {spec['email']} already exists.")
            # Reconcile org_id pra o caso de a coluna ter vindo NULL de seeds
            # anteriores.
            if existing.organization_id != desired_org_id:
                existing.organization_id = desired_org_id
            for role in spec["roles"]:
                grant_role(session, user_id=existing.id, role=role)
            out[spec["email"]] = (existing, list(spec["roles"]))
            continue

        user = User(
            organization_id=desired_org_id,
            name=spec["name"],
            email=spec["email"],
            phone=None,
            password_hash=hash_password(DEFAULT_PASSWORD),
            verified=True,
        )
        session.add(user)
        session.flush()
        for role in spec["roles"]:
            grant_role(session, user_id=user.id, role=role)
        out[spec["email"]] = (user, list(spec["roles"]))
        role_label = ",".join(r.value for r in spec["roles"])
        print(f"[seed] created user {spec['email']} (roles={role_label})")
    return out


def seed_crises(session, *, author_id) -> list[Crisis]:
    """Insert sample crises owned by `author_id`. Returns the full list of
    seed crises (existing + newly inserted)."""
    rows: list[Crisis] = []
    inserted = 0
    for data in CRISES_SPEC:
        existing = session.scalar(select(Crisis).where(Crisis.name == data["name"]))
        if existing is not None:
            rows.append(existing)
            continue
        crisis = Crisis(**data, created_by=author_id)
        session.add(crisis)
        session.flush()
        rows.append(crisis)
        inserted += 1
    if inserted:
        print(f"[seed] {inserted} new crises created.")
    else:
        print("[seed] all sample crises already exist.")
    return rows


def seed_shelters(
    session,
    *,
    organization_id: UUID,
    responsible_user_id,
    created_by,
    verified_by,
) -> list[Shelter]:
    """Insert sample shelters. Returns existing + newly inserted shelters.

    Reconcilia o `organization_id` em shelters pré-existentes — necessário
    quando o seed evoluiu (org_id era NULL em seeds antigos).
    """
    rows: list[Shelter] = []
    inserted = 0
    for spec in SHELTERS_SPEC:
        existing = session.scalar(select(Shelter).where(Shelter.name == spec["name"]))
        if existing is not None:
            if existing.organization_id != organization_id:
                existing.organization_id = organization_id
            rows.append(existing)
            continue

        data = {
            **spec,
            "organization_id": organization_id,
            "responsible_user_id": responsible_user_id,
            "created_by": created_by,
            "verified_by": verified_by if spec["verified"] else None,
        }
        shelter = Shelter(**data)
        session.add(shelter)
        session.flush()
        rows.append(shelter)
        inserted += 1
    if inserted:
        print(f"[seed] {inserted} new shelters created.")
    else:
        print("[seed] all sample shelters already exist.")
    return rows


def seed_categories(session) -> list[ResourceCategory]:
    """Get-or-create the curated taxonomy of resource categories.

    Idempotent: skip rows whose `name` already exists in the table.
    """
    inserted = 0
    rows: list[ResourceCategory] = []
    for name, unit, lot_category, description in CATEGORIES_SPEC:
        existing = session.scalar(
            select(ResourceCategory).where(ResourceCategory.name == name)
        )
        if existing is not None:
            rows.append(existing)
            continue
        category = ResourceCategory(
            name=name,
            unit=unit,
            lot_category=lot_category,
            description=description,
        )
        session.add(category)
        session.flush()
        rows.append(category)
        inserted += 1
    if inserted:
        print(f"[seed] {inserted} new resource categories created.")
    else:
        print("[seed] all sample resource categories already exist.")
    return rows


def grant_scope(session, *, crisis_manager_user_id, crises: list[Crisis]) -> None:
    """Populate users_crises for the crisis_manager seed user, idempotent."""
    granted = 0
    for c in crises:
        existing = session.scalar(
            select(UsersCrises).where(
                UsersCrises.user_id == crisis_manager_user_id,
                UsersCrises.crisis_id == c.id,
            )
        )
        if existing is not None:
            continue
        session.add(UsersCrises(user_id=crisis_manager_user_id, crisis_id=c.id))
        granted += 1
    if granted:
        print(f"[seed] granted scope on {granted} crises to crisis_manager.")


def link_crises_shelters(
    session,
    *,
    crises: list[Crisis],
    shelters: list[Shelter],
) -> None:
    """Populate crises_shelters links for sample data, idempotent."""
    crises_by_name = {c.name: c for c in crises}
    shelters_by_name = {s.name: s for s in shelters}
    linked = 0

    for crisis_name, shelter_names in CRISIS_SHELTER_LINKS.items():
        crisis = crises_by_name.get(crisis_name)
        if crisis is None:
            raise RuntimeError(
                f"Seed link references unknown crisis: {crisis_name!r}. "
                "Check CRISIS_SHELTER_LINKS and CRISES_SPEC."
            )

        for shelter_name in shelter_names:
            shelter = shelters_by_name.get(shelter_name)
            if shelter is None:
                raise RuntimeError(
                    f"Seed link references unknown shelter: {shelter_name!r}. "
                    "Check CRISIS_SHELTER_LINKS and SHELTERS_SPEC."
                )

            existing = session.scalar(
                select(CrisesShelters).where(
                    CrisesShelters.crisis_id == crisis.id,
                    CrisesShelters.shelter_id == shelter.id,
                )
            )
            if existing is not None:
                continue

            session.add(
                CrisesShelters(
                    crisis_id=crisis.id,
                    shelter_id=shelter.id,
                )
            )
            linked += 1

    if linked:
        print(f"[seed] linked {linked} crisis/shelter pairs.")
    else:
        print("[seed] all crisis/shelter links already exist.")


def assign_managers_to_shelters(
    session,
    *,
    shelters: list[Shelter],
    users_by_email: dict[str, tuple[User, list[Role]]],
    granted_by: UUID,
) -> None:
    """Wire users_shelters pra cada (shelter, manager) em SHELTER_MANAGER_ASSIGNMENTS.

    Cada linha em users_shelters conta como 1 `active_managers` no dashboard.
    """
    shelters_by_name = {s.name: s for s in shelters}
    inserted = 0
    for shelter_name, manager_emails in SHELTER_MANAGER_ASSIGNMENTS.items():
        shelter = shelters_by_name.get(shelter_name)
        if shelter is None:
            continue
        for email in manager_emails:
            user_tuple = users_by_email.get(email)
            if user_tuple is None:
                print(
                    f"[seed] WARN assigning manager {email!r} to {shelter_name!r}: "
                    "user nao encontrado, pulando."
                )
                continue
            user = user_tuple[0]
            existing = session.scalar(
                select(UsersShelters).where(
                    UsersShelters.user_id == user.id,
                    UsersShelters.shelter_id == shelter.id,
                )
            )
            if existing is not None:
                continue
            session.add(
                UsersShelters(
                    user_id=user.id,
                    shelter_id=shelter.id,
                    granted_by=granted_by,
                )
            )
            inserted += 1
    if inserted:
        print(f"[seed] {inserted} users_shelters rows created.")
    else:
        print("[seed] all manager assignments already exist.")


def seed_inventory_items(
    session,
    *,
    shelters: list[Shelter],
    categories: list[ResourceCategory],
) -> None:
    """Popula `inventory_items` pra cada (shelter, category) listado em
    INVENTORY_ITEMS_SPEC. Idempotente via unique (shelter_id, category_id).
    """
    shelters_by_name = {s.name: s for s in shelters}
    categories_by_name = {c.name: c for c in categories}
    inserted = 0

    for shelter_name, category_name, qty_current, qty_max in INVENTORY_ITEMS_SPEC:
        shelter = shelters_by_name.get(shelter_name)
        category = categories_by_name.get(category_name)
        if shelter is None or category is None:
            print(
                f"[seed] WARN inventory_item skip {shelter_name!r}/{category_name!r}: "
                "referencia ausente."
            )
            continue
        existing = session.scalar(
            select(InventoryItem).where(
                InventoryItem.shelter_id == shelter.id,
                InventoryItem.category_id == category.id,
            )
        )
        if existing is not None:
            # Reconcilia quantidades pra o caso do seed ter evoluido.
            existing.quantity_current = qty_current
            existing.quantity_max = qty_max
            continue
        session.add(
            InventoryItem(
                shelter_id=shelter.id,
                category_id=category.id,
                quantity_current=qty_current,
                quantity_max=qty_max,
            )
        )
        inserted += 1
    if inserted:
        print(f"[seed] {inserted} inventory_items created.")
    else:
        print("[seed] all inventory_items already exist (reconciled quantities).")


def seed_inventory_movements(
    session,
    *,
    shelters: list[Shelter],
    categories: list[ResourceCategory],
    actor_id: UUID,
) -> None:
    """Insere `inventory_movements` historicos (sem usar record_movement, pra
    nao mexer no inventory_items.quantity_current — esse ja foi seedado direto).

    Como movements nao tem natural unique key, a estrategia é: se ja existir
    qualquer movement com (shelter_id, category_id, direction, quantity, reason),
    assume que ta seedado e pula.
    """
    shelters_by_name = {s.name: s for s in shelters}
    categories_by_name = {c.name: c for c in categories}
    inserted = 0

    for (
        shelter_name,
        category_name,
        direction,
        quantity,
        reason,
        source,
        destination_name,
    ) in INVENTORY_MOVEMENTS_SPEC:
        shelter = shelters_by_name.get(shelter_name)
        category = categories_by_name.get(category_name)
        if shelter is None or category is None:
            continue

        destination_shelter_id = None
        if destination_name is not None:
            dest = shelters_by_name.get(destination_name)
            if dest is None:
                print(
                    f"[seed] WARN movement skip dest {destination_name!r}: "
                    "referencia ausente."
                )
                continue
            destination_shelter_id = dest.id

        existing = session.scalar(
            select(InventoryMovement).where(
                InventoryMovement.shelter_id == shelter.id,
                InventoryMovement.category_id == category.id,
                InventoryMovement.direction == direction,
                InventoryMovement.quantity == quantity,
                InventoryMovement.reason == reason,
            )
        )
        if existing is not None:
            continue

        session.add(
            InventoryMovement(
                shelter_id=shelter.id,
                category_id=category.id,
                direction=direction,
                quantity=quantity,
                reason=reason,
                source=source,
                notes=None,
                destination_shelter_id=destination_shelter_id,
                created_by=actor_id,
            )
        )
        inserted += 1
    if inserted:
        print(f"[seed] {inserted} inventory_movements created.")
    else:
        print("[seed] all inventory_movements already exist.")


def seed_beneficiaries_and_stays(
    session,
    *,
    shelters: list[Shelter],
) -> None:
    """Insere beneficiarios e abre um shelter_stay por beneficiario, segundo
    o `shelter_name` declarado em cada entry de BENEFICIARIES_SPEC.
    """
    shelters_by_name = {s.name: s for s in shelters}
    inserted_b = 0
    inserted_s = 0
    check_in = datetime.now(timezone.utc)

    for spec in BENEFICIARIES_SPEC:
        shelter_name = spec["shelter_name"]
        shelter = shelters_by_name.get(shelter_name)
        if shelter is None:
            print(f"[seed] WARN beneficiary skip — shelter {shelter_name!r} ausente.")
            continue

        beneficiary = session.scalar(
            select(Beneficiary).where(Beneficiary.cpf == spec["cpf"])
        )
        if beneficiary is None:
            beneficiary = Beneficiary(
                user_id=None,
                cpf=spec["cpf"],
                name=spec["name"],
                age=spec["age"],
                vulnerability=spec["vulnerability"],
                notes=spec.get("notes"),
            )
            session.add(beneficiary)
            session.flush()
            inserted_b += 1

        # Open stay (checked_out_at IS NULL) — usado pelo dashboard pra contar
        # "pessoas no abrigo agora".
        existing_stay = session.scalar(
            select(ShelterStay).where(
                ShelterStay.beneficiary_id == beneficiary.id,
                ShelterStay.shelter_id == shelter.id,
                ShelterStay.checked_out_at.is_(None),
            )
        )
        if existing_stay is None:
            session.add(
                ShelterStay(
                    beneficiary_id=beneficiary.id,
                    shelter_id=shelter.id,
                    checked_in_at=check_in,
                    checked_out_at=None,
                )
            )
            inserted_s += 1

    if inserted_b:
        print(f"[seed] {inserted_b} beneficiaries created.")
    if inserted_s:
        print(f"[seed] {inserted_s} shelter_stays opened.")
    if not (inserted_b or inserted_s):
        print("[seed] all beneficiaries and stays already exist.")


def seed_demo_full_shelter(
    session,
    *,
    shelters: list[Shelter],
    categories: list[ResourceCategory],
    actor_id,
) -> None:
    """Reforça o estoque e as pessoas do DEMO_FULL_SHELTER pra a feature de
    planilha. Idempotente: se ja existir inventory_item ou open stay, skip.

    Funciona em cima do que `seed_inventory_items` e `seed_beneficiaries_and_stays`
    deixaram — adiciona o que falta. Inventory é adicionado via record_movement
    (entrada como `donation`) pra historicizar.
    """
    shelters_by_name = {s.name: s for s in shelters}
    categories_by_name = {c.name: c for c in categories}
    shelter = shelters_by_name.get(DEMO_FULL_SHELTER_NAME)
    if shelter is None:
        raise RuntimeError(
            f"Seed full shelter references unknown shelter: {DEMO_FULL_SHELTER_NAME!r}."
        )

    inventory_service = InventoryService(session)
    resources_created = 0
    for category_name, quantity in DEMO_FULL_SHELTER_INVENTORY.items():
        category = categories_by_name.get(category_name)
        if category is None:
            raise RuntimeError(
                f"Seed inventory references unknown category: {category_name!r}."
            )

        existing_item = inventory_service.items.get_for_shelter_category(
            shelter_id=shelter.id,
            category_id=category.id,
        )
        if existing_item is not None:
            continue

        inventory_service.record_movement(
            shelter_id=shelter.id,
            actor_id=actor_id,
            payload=InventoryMovementCreateRequest(
                category_id=category.id,
                direction=MovementDirection.IN,
                quantity=quantity,
                reason=MovementReason.DONATION,
                source="seed",
                notes="Seed inicial para demonstracao de planilha do abrigo.",
            ),
        )
        resources_created += 1

    # Pessoas: o spreadsheet feature exige que TODAS as entries em
    # BENEFICIARIES_SPEC tenham um open stay no demo shelter. Filtrar por
    # shelter_name aqui quebraria o test_seed_demo_full_shelter_open_stay_is
    # _scoped_to_shelter — entao adicionamos todos, idempotentemente.
    people_created = 0
    stays_created = 0
    for spec in BENEFICIARIES_SPEC:
        beneficiary = session.scalar(
            select(Beneficiary).where(Beneficiary.cpf == spec["cpf"])
        )
        if beneficiary is None:
            beneficiary = Beneficiary(
                id=uuid4(),
                user_id=None,
                cpf=spec["cpf"],
                name=spec["name"],
                age=spec["age"],
                vulnerability=spec["vulnerability"],
                notes=spec.get("notes"),
            )
            session.add(beneficiary)
            session.flush()
            people_created += 1

        open_stay = session.scalar(
            select(ShelterStay).where(
                ShelterStay.beneficiary_id == beneficiary.id,
                ShelterStay.shelter_id == shelter.id,
                ShelterStay.checked_out_at.is_(None),
            )
        )
        if open_stay is None:
            session.add(
                ShelterStay(
                    id=uuid4(),
                    beneficiary_id=beneficiary.id,
                    shelter_id=shelter.id,
                )
            )
            stays_created += 1

    if resources_created or people_created or stays_created:
        print(
            "[seed] demo shelter populated: "
            f"{resources_created} resources, "
            f"{people_created} people, "
            f"{stays_created} active stays."
        )
    else:
        print("[seed] demo shelter inventory and people already exist.")


# -------------------------------------------------------------------------- #
# Pretty print                                                               #
# -------------------------------------------------------------------------- #


def print_credentials(users: dict[str, tuple[User, list[Role]]]) -> None:
    print()
    print("=== Usuarios seeded ===")
    print(f"Senha (para todos): {DEFAULT_PASSWORD}")
    print("Se a senha nao funcionar, rode o seed com --reset.\n")
    print("=== JWTs (validos por 24h) ===")
    for spec in USERS_SPEC:
        user, roles = users[spec["email"]]
        token, _ = create_access_token(
            user_id=user.id,
            roles=roles,
            organization_id=user.organization_id,
        )
        role_label = ",".join(r.value for r in roles)
        print(f"\n[{role_label}]")
        print(f"  email:   {user.email}")
        print(f"  user_id: {user.id}")
        print(f"  org_id:  {user.organization_id}")
        print(f"  token:   {token}")
    print()
    print("Uso:")
    print("  - Cola o JWT em 'Authorize' no Swagger (/api/docs): Bearer <token>")
    print("  - Ou faz POST /auth/login com email+senha pra obter um token novo")


# -------------------------------------------------------------------------- #
# Runner                                                                     #
# -------------------------------------------------------------------------- #


def run(reset_first: bool) -> int:
    with SessionLocal() as session:
        try:
            if reset_first:
                reset(session)

            org_id = seed_organization(session)
            session.commit()

            users = seed_users(session, organization_id=org_id)
            session.commit()

            dev_user, _ = users["admin@horizonteseguro.app"]
            crisis_mgr, _ = users["gestor.crise@horizonteseguro.app"]
            shelter_mgr, _ = users["gestor.abrigo@horizonteseguro.app"]

            crises = seed_crises(session, author_id=dev_user.id)
            session.commit()

            shelters = seed_shelters(
                session,
                organization_id=org_id,
                responsible_user_id=shelter_mgr.id,
                created_by=dev_user.id,
                verified_by=dev_user.id,
            )
            session.commit()

            grant_scope(
                session,
                crisis_manager_user_id=crisis_mgr.id,
                crises=crises,
            )
            link_crises_shelters(session, crises=crises, shelters=shelters)
            session.commit()

            categories = seed_categories(session)
            session.commit()

            assign_managers_to_shelters(
                session,
                shelters=shelters,
                users_by_email=users,
                granted_by=dev_user.id,
            )
            seed_inventory_items(session, shelters=shelters, categories=categories)
            seed_inventory_movements(
                session,
                shelters=shelters,
                categories=categories,
                actor_id=dev_user.id,
            )
            seed_beneficiaries_and_stays(session, shelters=shelters)
            # Reforço final: garante que o DEMO_FULL_SHELTER tem TODAS as 11
            # categorias e que TODOS os beneficiaries seedados estao tambem
            # acolhidos lá (pre-requisito do spreadsheet feature).
            seed_demo_full_shelter(
                session,
                shelters=shelters,
                categories=categories,
                actor_id=dev_user.id,
            )
            session.commit()

            print_credentials(users)
        except Exception:
            session.rollback()
            raise
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Delete previously-seeded users, crises, shelters, inventory, "
            "beneficiaries and organization before inserting."
        ),
    )
    args = parser.parse_args()
    return run(reset_first=args.reset)


if __name__ == "__main__":
    sys.exit(main())
