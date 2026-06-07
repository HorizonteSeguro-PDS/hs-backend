from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.audit.enums import AuditAction, AuditEntityType
from domain.crisis.enums import CrisisStatus, CrisisType
from domain.crisis.schemas import CrisisClose, CrisisCreate, CrisisRead, CrisisUpdate
from domain.models.crisis import Crisis
from services.audit_service import audit_event


router = APIRouter(prefix="/crises", tags=["crises"])

# Reads are open to any authenticated role (scope filtering will come in a
# follow-up story — see PHS-XX). Writes are gated to dev and crisis_manager;
# shelter_manager / sheltered cannot create or mutate crises.
_ReadDep = Annotated[
    CurrentUser,
    Depends(require_role("dev", "crisis_manager", "shelter_manager", "sheltered")),
]
_WriteDep = Annotated[CurrentUser, Depends(require_role("dev", "crisis_manager"))]
_SessionDep = Annotated[Session, Depends(get_session)]


@router.post("", response_model=CrisisRead, status_code=status.HTTP_201_CREATED)
def create_crisis(
    payload: CrisisCreate,
    session: _SessionDep,
    user: _WriteDep,
) -> Crisis:
    crisis = Crisis(**payload.model_dump(), created_by=user.id)
    session.add(crisis)
    session.flush()

    audit_event(
        session,
        entity_type=AuditEntityType.CRISIS.value,
        entity_id=crisis.id,
        action=AuditAction.CREATE.value,
        author_id=user.id,
        payload=payload.model_dump(mode="json"),
    )

    session.commit()
    session.refresh(crisis)
    return crisis


@router.get("", response_model=list[CrisisRead])
def list_crises(
    session: _SessionDep,
    _user: _ReadDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[CrisisStatus | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    type: Annotated[CrisisType | None, Query()] = None,
) -> list[Crisis]:
    stmt = select(Crisis).order_by(Crisis.created_at.desc()).limit(limit).offset(offset)
    if status is not None:
        stmt = stmt.where(Crisis.status == status)
    if state is not None:
        stmt = stmt.where(Crisis.state == state)
    if type is not None:
        stmt = stmt.where(Crisis.type == type)
    return list(session.scalars(stmt))


@router.get(
    "/{crisis_id}",
    response_model=CrisisRead,
    responses={404: {"description": "crisis not found"}},
)
def get_crisis(
    crisis_id: UUID,
    session: _SessionDep,
    _user: _ReadDep,
) -> Crisis:
    crisis = session.get(Crisis, crisis_id)
    if not crisis:
        raise HTTPException(status_code=404, detail="crisis not found")
    return crisis


@router.patch(
    "/{crisis_id}",
    response_model=CrisisRead,
    responses={404: {"description": "crisis not found"}},
)
def update_crisis(
    crisis_id: UUID,
    payload: CrisisUpdate,
    session: _SessionDep,
    user: _WriteDep,
) -> Crisis:
    crisis = session.get(Crisis, crisis_id)
    if not crisis:
        raise HTTPException(status_code=404, detail="crisis not found")

    updates = payload.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(crisis, field, value)

    audit_event(
        session,
        entity_type=AuditEntityType.CRISIS.value,
        entity_id=crisis.id,
        action=AuditAction.UPDATE.value,
        author_id=user.id,
        payload=payload.model_dump(mode="json", exclude_none=True),
    )

    session.commit()
    session.refresh(crisis)
    return crisis


@router.post(
    "/{crisis_id}/close",
    response_model=CrisisRead,
    responses={
        404: {"description": "crisis not found"},
        409: {"description": "crisis already closed"},
    },
)
def close_crisis(
    crisis_id: UUID,
    payload: CrisisClose,
    session: _SessionDep,
    user: _WriteDep,
) -> Crisis:
    crisis = session.get(Crisis, crisis_id)
    if not crisis:
        raise HTTPException(status_code=404, detail="crisis not found")
    if crisis.status == CrisisStatus.CLOSED:
        raise HTTPException(status_code=409, detail="crisis already closed")

    crisis.status = CrisisStatus.CLOSED
    crisis.closed_at = datetime.now(timezone.utc)
    crisis.closed_by = user.id
    crisis.close_reason = payload.close_reason

    audit_event(
        session,
        entity_type=AuditEntityType.CRISIS.value,
        entity_id=crisis.id,
        action=AuditAction.CLOSE.value,
        author_id=user.id,
        payload={"close_reason": payload.close_reason},
    )

    session.commit()
    session.refresh(crisis)
    return crisis


@router.post(
    "/{crisis_id}/reopen",
    response_model=CrisisRead,
    responses={
        404: {"description": "crisis not found"},
        409: {"description": "crisis already active"},
    },
)
def reopen_crisis(
    crisis_id: UUID,
    session: _SessionDep,
    user: _WriteDep,
) -> Crisis:
    crisis = session.get(Crisis, crisis_id)
    if not crisis:
        raise HTTPException(status_code=404, detail="crisis not found")
    if crisis.status == CrisisStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="crisis already active")

    crisis.status = CrisisStatus.ACTIVE
    crisis.closed_at = None
    crisis.closed_by = None
    crisis.close_reason = None

    audit_event(
        session,
        entity_type=AuditEntityType.CRISIS.value,
        entity_id=crisis.id,
        action=AuditAction.REOPEN.value,
        author_id=user.id,
        payload=None,
    )

    session.commit()
    session.refresh(crisis)
    return crisis
