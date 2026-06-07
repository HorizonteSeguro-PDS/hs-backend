"""User management endpoints. Gated by Role.MASTER."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.audit.enums import AuditAction, AuditEntityType
from domain.models.user import User
from domain.user.schemas import UserRead, UserRegister
from services.audit_service import audit_event
from services.auth_service import ensure_role, hash_password

router = APIRouter(prefix="/users", tags=["users"])

_MasterOnly = Annotated[CurrentUser, Depends(require_role("master"))]
_SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "missing or invalid bearer token"},
        403: {"description": "only master can register users"},
        409: {"description": "email already registered"},
    },
)
def register_user(
    payload: UserRegister,
    session: _SessionDep,
    actor: _MasterOnly,
) -> UserRead:
    """
    Create a new user. Requires a master token.

    The first master must be bootstrapped via `scripts/create_master.py`
    (which writes directly to the database, bypassing this endpoint).
    """
    role_row = ensure_role(session, payload.role)

    user = User(
        role_id=role_row.id,
        organization_id=payload.organization_id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        verified=False,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        ) from exc

    audit_event(
        session,
        entity_type=AuditEntityType.USER.value,
        entity_id=user.id,
        action=AuditAction.CREATE.value,
        author_id=actor.id,
        payload={"email": user.email, "role": payload.role.value},
    )

    session.commit()
    session.refresh(user)

    return UserRead(
        id=user.id,
        name=user.name,
        email=user.email,
        role=payload.role,
        organization_id=user.organization_id,
        phone=user.phone,
        verified=user.verified,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )
