import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.auth.enums import Role
from domain.models.organization import Organization
from domain.models.registration_request import RegistrationRequest
from domain.models.user import User
from domain.registration.schemas import (
    ExistingOrganizationRegistrationRequest,
    NewOrganizationRegistrationRequest,
    RegistrationRequestRead,
)
from domain.schemas.enums import OrganizationType
from services.auth_service import can_create_roles, grant_role, hash_password
from services.email_service import send_registration_approved_email

router = APIRouter(prefix="/registration-requests", tags=["registration-requests"])
logger = logging.getLogger("uvicorn.error")

_SessionDep = Annotated[Session, Depends(get_session)]
_ReviewerDep = Annotated[
    CurrentUser,
    Depends(require_role("dev", "crisis_manager")),
]

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
TYPE_EXISTING_ORGANIZATION = "existing_organization"
TYPE_NEW_ORGANIZATION = "new_organization"


def _pending_request_by_email(
    session: Session, email: str
) -> RegistrationRequest | None:
    return session.scalar(
        select(RegistrationRequest).where(
            RegistrationRequest.email == email,
            RegistrationRequest.status == STATUS_PENDING,
        )
    )


def _ensure_email_available(session: Session, email: str) -> None:
    if session.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )
    if _pending_request_by_email(session, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="registration request already pending",
        )


def _existing_organization_by_name(session: Session, name: str) -> Organization | None:
    return session.scalar(
        select(Organization).where(func.lower(Organization.name) == name.lower())
    )


def _pending_new_organization_by_name(
    session: Session, name: str, exclude_request_id: UUID | None = None
) -> RegistrationRequest | None:
    stmt = select(RegistrationRequest).where(
        RegistrationRequest.status == STATUS_PENDING,
        RegistrationRequest.request_type == TYPE_NEW_ORGANIZATION,
        func.lower(RegistrationRequest.new_organization_name) == name.lower(),
    )
    if exclude_request_id is not None:
        stmt = stmt.where(RegistrationRequest.id != exclude_request_id)
    return session.scalar(stmt)


def _ensure_new_organization_available(
    session: Session, name: str, exclude_request_id: UUID | None = None
) -> None:
    if _existing_organization_by_name(session, name) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="organization already exists",
        )
    if _pending_new_organization_by_name(session, name, exclude_request_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="organization registration request already pending",
        )


def _request_roles(registration_request: RegistrationRequest) -> list[Role]:
    roles: list[Role] = []
    for raw_role in registration_request.roles:
        role = raw_role if isinstance(raw_role, Role) else Role(raw_role)
        if role is Role.DEV:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="registration request contains a forbidden role",
            )
        roles.append(role)
    return roles


def _raise_for_unauthorized_roles(actor: CurrentUser, roles: list[Role]) -> None:
    if can_create_roles(actor.roles, roles):
        return
    actor_label = ",".join(sorted(role.value for role in actor.roles)) or "(none)"
    target_label = ",".join(sorted(role.value for role in roles))
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"roles [{actor_label}] cannot create one or more of [{target_label}]",
    )


def _finalize_request(
    session: Session,
    registration_request: RegistrationRequest,
    actor: CurrentUser,
) -> RegistrationRequestRead:
    now = datetime.now(timezone.utc)
    registration_request.status = STATUS_APPROVED
    registration_request.reviewed_by = actor.id
    registration_request.reviewed_at = now

    session.commit()
    session.refresh(registration_request)
    return RegistrationRequestRead.model_validate(registration_request)


@router.post(
    "/existing-organization",
    response_model=RegistrationRequestRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "organization not found"},
        409: {"description": "email already registered or request already pending"},
    },
)
def create_existing_organization_request(
    payload: ExistingOrganizationRegistrationRequest,
    session: _SessionDep,
) -> RegistrationRequestRead:
    organization = session.get(Organization, payload.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="organization not found",
        )

    email = str(payload.email)
    _ensure_email_available(session, email)

    registration_request = RegistrationRequest(
        status=STATUS_PENDING,
        request_type=TYPE_EXISTING_ORGANIZATION,
        name=payload.name,
        email=email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        roles=[role.value for role in payload.roles],
        organization_id=organization.id,
    )
    session.add(registration_request)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="registration request could not be created",
        ) from exc
    session.refresh(registration_request)
    return RegistrationRequestRead.model_validate(registration_request)


@router.post(
    "/new-organization",
    response_model=RegistrationRequestRead,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "email or organization already pending/exists"}},
)
def create_new_organization_request(
    payload: NewOrganizationRegistrationRequest,
    session: _SessionDep,
) -> RegistrationRequestRead:
    email = str(payload.email)
    _ensure_email_available(session, email)
    _ensure_new_organization_available(session, payload.organization_name)

    registration_request = RegistrationRequest(
        status=STATUS_PENDING,
        request_type=TYPE_NEW_ORGANIZATION,
        name=payload.name,
        email=email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        roles=[role.value for role in payload.roles],
        new_organization_name=payload.organization_name,
        new_organization_cnpj=payload.organization_cnpj,
        new_organization_type=payload.organization_type.value,
        new_organization_contact_email=(
            str(payload.organization_contact_email)
            if payload.organization_contact_email is not None
            else None
        ),
    )
    session.add(registration_request)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="registration request could not be created",
        ) from exc
    session.refresh(registration_request)
    return RegistrationRequestRead.model_validate(registration_request)


@router.get("", response_model=list[RegistrationRequestRead])
def list_registration_requests(
    session: _SessionDep,
    _actor: _ReviewerDep,
) -> list[RegistrationRequestRead]:
    rows = session.scalars(
        select(RegistrationRequest).order_by(RegistrationRequest.created_at.desc())
    ).all()
    return [RegistrationRequestRead.model_validate(row) for row in rows]


@router.post(
    "/{registration_request_id}/approve",
    response_model=RegistrationRequestRead,
    responses={
        403: {"description": "role not authorized for this operation"},
        404: {"description": "registration request not found"},
        409: {"description": "registration request already reviewed"},
    },
)
def approve_registration_request(
    registration_request_id: UUID,
    session: _SessionDep,
    actor: _ReviewerDep,
) -> RegistrationRequestRead:
    registration_request = session.get(RegistrationRequest, registration_request_id)
    if registration_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="registration request not found",
        )
    if registration_request.status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="registration request already reviewed",
        )
    if session.scalar(select(User).where(User.email == registration_request.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already registered",
        )

    roles = _request_roles(registration_request)
    _raise_for_unauthorized_roles(actor, roles)
    organization_id = registration_request.organization_id

    if registration_request.request_type == TYPE_EXISTING_ORGANIZATION:
        if (
            organization_id is None
            or session.get(Organization, organization_id) is None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="organization not found",
            )
    elif registration_request.request_type == TYPE_NEW_ORGANIZATION:
        if registration_request.new_organization_name is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="registration request missing organization data",
            )
        _ensure_new_organization_available(
            session,
            registration_request.new_organization_name,
            exclude_request_id=registration_request.id,
        )
        organization = Organization(
            name=registration_request.new_organization_name,
            cnpj=registration_request.new_organization_cnpj,
            type=OrganizationType(registration_request.new_organization_type),
            contact_email=registration_request.new_organization_contact_email,
        )
        session.add(organization)
        session.flush()
        organization_id = organization.id
        registration_request.created_organization_id = organization.id
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="unsupported registration request type",
        )

    user = User(
        organization_id=organization_id,
        name=registration_request.name,
        email=registration_request.email,
        phone=registration_request.phone,
        password_hash=registration_request.password_hash,
        verified=True,
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

    for role in roles:
        grant_role(session, user_id=user.id, role=role)

    registration_request.user_id = user.id
    response = _finalize_request(session, registration_request, actor)
    try:
        send_registration_approved_email(
            to=registration_request.email,
            name=registration_request.name,
        )
    except Exception:
        logger.exception(
            "failed to send registration approval email for request %s",
            registration_request.id,
        )
    return response


@router.post(
    "/{registration_request_id}/reject",
    response_model=RegistrationRequestRead,
    responses={
        403: {"description": "role not authorized for this operation"},
        404: {"description": "registration request not found"},
        409: {"description": "registration request already reviewed"},
    },
)
def reject_registration_request(
    registration_request_id: UUID,
    session: _SessionDep,
    actor: _ReviewerDep,
) -> RegistrationRequestRead:
    registration_request = session.get(RegistrationRequest, registration_request_id)
    if registration_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="registration request not found",
        )
    if registration_request.status != STATUS_PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="registration request already reviewed",
        )

    registration_request.status = STATUS_REJECTED
    registration_request.reviewed_by = actor.id
    registration_request.reviewed_at = datetime.now(timezone.utc)

    session.commit()
    session.refresh(registration_request)
    return RegistrationRequestRead.model_validate(registration_request)
