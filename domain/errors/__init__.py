"""Domain errors package."""

from domain.errors.http import (
    ForbiddenRequestError,
    GenericError,
    InternalError,
    KeyNotFoundError,
    ResourceAlreadyExists,
    ResourceInUse,
    ResourceNotFoundError,
)

__all__ = [
    "ForbiddenRequestError",
    "GenericError",
    "InternalError",
    "KeyNotFoundError",
    "ResourceAlreadyExists",
    "ResourceInUse",
    "ResourceNotFoundError",
]
