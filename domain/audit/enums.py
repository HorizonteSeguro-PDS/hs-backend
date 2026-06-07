from enum import Enum


class AuditAction(str, Enum):
    """Mirrors the `audit_action` Postgres enum defined in migration 0003."""

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
    """Mirrors the `audit_entity_type` Postgres enum defined in migration 0003."""

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
