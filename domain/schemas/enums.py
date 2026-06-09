from enum import Enum


class RoleScope(str, Enum):
    GLOBAL = "global"
    ORGANIZATION = "organization"
    CRISIS = "crisis"
    SHELTER = "shelter"


class ResourceUnit(str, Enum):
    """Unit of measure for a ResourceCategory.

    Mirrors the `resource_unit` Postgres enum defined in migration 0013.
    """

    KG = "kg"
    G = "g"
    L = "L"
    ML = "mL"
    UNIDADE = "unidade"
    REAL = "real"


class LotCategory(str, Enum):
    """Bucket grosseiro de tipo de recurso — categoria-pai das
    ResourceCategory mais específicas. Combinado com o front em iteração.

    Mirrors the `lot_category` Postgres enum (originalmente 9 valores na
    0018, reduzido pra 6 valores mais focados na 0021).

    Grupos e exemplos de itens:
      ESSENCIAIS        — alimento, água potável, roupa, cobertor, colchão,
                          kit higiene, kit limpeza
      SAUDE             — medicamento, material médico, primeiros socorros,
                          serviço de saúde, serviço psicológico
      INFANTIL_E_IDOSOS — fralda infantil, fralda geriátrica, absorvente,
                          brinquedo infantil
      ANIMAIS           — ração animal, caixa de transporte, serviço
                          veterinário
      INFRAESTRUTURA    — lanterna, pilha/bateria, carregador, power bank,
                          gerador, lona, tenda/barraca, botijão de gás
      OPERACAO          — voluntário, transporte, equipamento de resgate,
                          material de sinalização, doação financeira
    """

    ESSENCIAIS = "essenciais"
    SAUDE = "saude"
    INFANTIL_E_IDOSOS = "infantil_e_idosos"
    ANIMAIS = "animais"
    INFRAESTRUTURA = "infraestrutura"
    OPERACAO = "operacao"


class SupplyStatus(str, Enum):
    """Label de saude do estoque, derivado de quantity_current/quantity_max.

    Pure Pydantic enum — NAO existe coluna nem CHECK no banco. A regra mora
    em services/operations.derive_supply_status.
    """

    SUFFICIENT = "Sufficient"
    LOW = "Low"
    CRITICAL = "Critical"


class MovementDirection(str, Enum):
    """Whether an inventory movement is an entry or exit.

    Mirrors the `movement_direction` Postgres enum defined in migration 0015.
    """

    IN = "in"
    OUT = "out"


class MovementReason(str, Enum):
    """Reason that justifies an inventory movement.

    Mirrors the `movement_reason` Postgres enum defined in migration 0015.
    """

    DONATION = "donation"  # entrada de doacao externa
    DISTRIBUTION = "distribution"  # saida pra beneficiarios
    TRANSFER_IN = "transfer_in"  # entrada vinda de outro abrigo
    TRANSFER_OUT = "transfer_out"  # saida pra outro abrigo
    ADJUSTMENT = "adjustment"  # ajuste de inventario (correcao)
    EXPIRED = "expired"  # saida por validade vencida
    OTHER = "other"


class OrganizationType(str, Enum):
    CRISIS_MANAGER = "crisis_manager"
    SHELTER_OPERATOR = "shelter_operator"
    DONOR = "donor"
    MIXED = "mixed"
    OTHER = "other"


class CrisisType(str, Enum):
    FLOOD = "flood"
    FIRE = "fire"
    LANDSLIDE = "landslide"
    DROUGHT = "drought"
    STORM = "storm"
    EPIDEMIC = "epidemic"
    OTHER = "other"


class CrisisStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class SeverityLabel(str, Enum):
    """Severity label shipped to the frontend.

    Backend stores severity as a small int (0-3); on response we map it to one
    of these labels (regra de negocio no back, conforme combinado com o front).

    Mapping:
        0 -> INATIVO   (sem ocupacao / crise inativa)
        1 -> BAIXA
        2 -> MEDIA
        3 -> ALTA
    """

    INATIVO = "INATIVO"
    BAIXA = "BAIXA"
    MEDIA = "MÉDIA"
    ALTA = "ALTA"


class BrazilianState(str, Enum):
    AC = "AC"
    AL = "AL"
    AP = "AP"
    AM = "AM"
    BA = "BA"
    CE = "CE"
    DF = "DF"
    ES = "ES"
    GO = "GO"
    MA = "MA"
    MT = "MT"
    MS = "MS"
    MG = "MG"
    PA = "PA"
    PB = "PB"
    PR = "PR"
    PE = "PE"
    PI = "PI"
    RJ = "RJ"
    RN = "RN"
    RS = "RS"
    RO = "RO"
    RR = "RR"
    SC = "SC"
    SP = "SP"
    SE = "SE"
    TO = "TO"


class ShelterType(str, Enum):
    INSTITUTIONAL = "institutional"
    COMMUNITY_HOME = "community_home"
    IMPROVISED_PUBLIC = "improvised_public"


class ShelterStatus(str, Enum):
    PREPARING = "preparing"
    ACTIVE = "active"
    FULL = "full"
    CLOSED = "closed"


class ShelterNeedStatus(str, Enum):
    OPEN = "open"
    PARTIALLY_FULFILLED = "partially_fulfilled"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class PriorityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VulnerabilityType(str, Enum):
    CHILD = "child"
    ELDERLY = "elderly"
    PREGNANT = "pregnant"
    DISABLED = "disabled"
    CHRONIC_ILLNESS = "chronic_illness"
    NONE = "none"
    OTHER = "other"


class DonationStatus(str, Enum):
    PLEDGED = "pledged"
    CONFIRMED = "confirmed"
    RECEIVED = "received"
    DISTRIBUTED = "distributed"
    CANCELLED = "cancelled"


class TransferType(str, Enum):
    EXTERNAL_DONATION = "external_donation"
    INTER_SHELTER = "inter_shelter"


class DistributionStatus(str, Enum):
    PLANNED = "planned"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class NotificationType(str, Enum):
    CRISIS_ALERT = "crisis_alert"
    NEED_DECLARED = "need_declared"
    NEED_CRITICAL = "need_critical"
    DONATION_PLEDGED = "donation_pledged"
    DONATION_RECEIVED = "donation_received"
    DISTRIBUTION_DISPATCHED = "distribution_dispatched"
    DISTRIBUTION_DELIVERED = "distribution_delivered"
    SHELTER_FULL = "shelter_full"
    SYSTEM = "system"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    REOPEN = "reopen"
    DELETE = "delete"
    VERIFY = "verify"
    PLEDGE = "pledge"
    CONFIRM = "confirm"
    DELIVER = "deliver"
    CANCEL = "cancel"
    LOGIN = "login"
    LOGOUT = "logout"


class AuditEntityType(str, Enum):
    ORGANIZATION = "ORGANIZATION"
    USER = "USER"
    ROLE = "ROLE"
    CRISIS = "CRISIS"
    SHELTER = "SHELTER"
    BENEFICIARY = "BENEFICIARY"
    SHELTER_NEED = "SHELTER_NEED"
    INVENTORY_ITEM = "INVENTORY_ITEM"
    DONATION = "DONATION"
    DISTRIBUTION = "DISTRIBUTION"
    NOTIFICATION = "NOTIFICATION"
