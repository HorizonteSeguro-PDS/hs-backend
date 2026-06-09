"""Authentication endpoints — login (open) for any registered user."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies.session import get_session
from domain.audit.enums import AuditAction, AuditEntityType
from domain.auth.schemas import LoginRequest, LoginResponse
from domain.user.schemas import UserRead
from services.audit_service import audit_event
from services.auth_service import authenticate, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

_SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"description": "invalid credentials"}},
)
def login(payload: LoginRequest, session: _SessionDep) -> LoginResponse:
    """
    Exchange email + password for a JWT.

    Same generic 401 for both unknown email and bad password — by design,
    to avoid leaking which emails exist.
    """
    result = authenticate(session, email=payload.email, password=payload.password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )
    user, roles = result
    if not user.verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )

    token, expires_in = create_access_token(
        user_id=user.id,
        roles=roles,
        organization_id=user.organization_id,
    )

    user.last_login_at = datetime.now(timezone.utc)

    audit_event(
        session,
        entity_type=AuditEntityType.USER.value,
        entity_id=user.id,
        action=AuditAction.LOGIN.value,
        author_id=user.id,
        payload=None,
    )

    session.commit()
    session.refresh(user)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserRead(
            id=user.id,
            name=user.name,
            email=user.email,
            roles=roles,
            organization_id=user.organization_id,
            phone=user.phone,
            verified=user.verified,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        ),
    )
