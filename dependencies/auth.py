from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domain.auth.jwt import CurrentUser, decode_jwt

_bearer = HTTPBearer(auto_error=False)

# Re-export for backward compatibility
__all__ = ["CurrentUser", "get_current_user", "require_role"]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_jwt(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*allowed_roles: str) -> Callable:
    """
    Factory that returns a FastAPI dependency enforcing role membership.

    Usage:
        @router.post("/crises")
        def create(user=Depends(require_role("master", "standard")), ...): ...
    """

    def dependency(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if user.role not in allowed_roles:
            # user.role is normally a Role enum; render its value (e.g. "master")
            # instead of "Role.MASTER". Fall back gracefully if it's a plain str.
            role_label = getattr(user.role, "value", user.role)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{role_label}' not authorized for this operation",
            )
        return user

    return dependency
