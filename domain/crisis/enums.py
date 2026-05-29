from enum import Enum


class CrisisStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class CrisisType(str, Enum):
    FLOOD = "flood"
    FIRE = "fire"
    LANDSLIDE = "landslide"
    OTHER = "other"
