from enum import Enum


class Role(str, Enum):
    """RBAC roles. Values are the strings carried in the JWT `roles` claim."""

    DEV = "dev"
    CRISIS_MANAGER = "crisis_manager"
    SHELTER_MANAGER = "shelter_manager"
    SHELTERED = "sheltered"
