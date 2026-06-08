from enum import Enum


class Role(str, Enum):
    """RBAC roles. Values are the strings carried in the JWT `roles` claim.

    Sheltered persons are NOT modelled as USERs — they live in the BENEFICIARY
    entity and don't log in. See migration 0009 for the enum cleanup.
    """

    DEV = "dev"
    CRISIS_MANAGER = "crisis_manager"
    SHELTER_MANAGER = "shelter_manager"
