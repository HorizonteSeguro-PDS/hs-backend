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

    Passes if ANY of the user's roles is in the allowed set.

    Usage:
        @router.post("/crises")
        def create(user=Depends(require_role("dev", "crisis_manager")), ...): ...
    """
    allowed = set(allowed_roles)

    def dependency(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        user_role_values = {getattr(r, "value", r) for r in user.roles}
        if not (user_role_values & allowed):
            roles_label = ",".join(sorted(user_role_values)) or "(none)"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(f"roles [{roles_label}] not authorized for this operation"),
            )
        return user

    return dependency
