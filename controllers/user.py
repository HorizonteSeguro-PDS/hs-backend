"""User management endpoints. Role-gated per the permissions matrix in
`services.auth_service.can_create_roles`."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, get_current_user
from dependencies.session import get_session
from domain.audit.enums import AuditAction, AuditEntityType
from domain.models.organization import Organization
from domain.models.user import User
from domain.user.schemas import UserRead, UserRegister
from services.audit_service import audit_event
from services.auth_service import (
    can_create_roles,
    grant_role,
    hash_password,
)

router = APIRouter(prefix="/users", tags=["users"])

_SessionDep = Annotated[Session, Depends(get_session)]
_CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "missing or invalid bearer token"},
        403: {
            "description": "actor not authorized to create one or more of the requested roles"
        },
        409: {"description": "email already registered"},
    },
)
def register_user(
    payload: UserRegister,
    session: _SessionDep,
    actor: _CurrentUserDep,
) -> UserRead:
    """
    Create a new user with one or more roles.

    Authorization rules (see `can_create_roles`):
      - dev             can create: dev, crisis_manager, shelter_manager
      - crisis_manager  can create: shelter_manager
      - shelter_manager can create nothing

    The first dev must be bootstrapped via `scripts/seed.py`.
    """
    if not can_create_roles(actor.roles, payload.roles):
        actor_label = ",".join(sorted(r.value for r in actor.roles)) or "(none)"
        target_label = ",".join(sorted(r.value for r in payload.roles))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"roles [{actor_label}] cannot create one or more of [{target_label}]"
            ),
        )

    if payload.organization_id is not None:
        if session.get(Organization, payload.organization_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="organization not found",
            )

    user = User(
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
        if "uq_users_email" in str(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="email already registered",
            ) from exc
        raise

    for role in payload.roles:
        grant_role(session, user_id=user.id, role=role)

    audit_event(
        session,
        entity_type=AuditEntityType.USER.value,
        entity_id=user.id,
        action=AuditAction.CREATE.value,
        author_id=actor.id,
        payload={
            "email": user.email,
            "roles": [r.value for r in payload.roles],
        },
    )

    session.commit()
    session.refresh(user)

    return UserRead(
        id=user.id,
        name=user.name,
        email=user.email,
        roles=payload.roles,
        organization_id=user.organization_id,
        phone=user.phone,
        verified=user.verified,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )
