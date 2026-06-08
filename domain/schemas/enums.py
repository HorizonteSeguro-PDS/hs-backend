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
