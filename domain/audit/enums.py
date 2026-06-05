from enum import Enum


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    REOPEN = "reopen"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"


class AuditEntityType(str, Enum):
    CRISIS = "CRISIS"
    AUDIT_LOG = "AUDIT_LOG"
