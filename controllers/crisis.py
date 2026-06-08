from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.audit.enums import AuditAction, AuditEntityType
from domain.crisis.enums import CrisisStatus, CrisisType
from domain.crisis.schemas import (
    CrisisClose,
    CrisisCreate,
    CrisisDetailResponse,
    CrisisListItemResponse,
    CrisisRead,
    CrisisUpdate,
)
from domain.models.crisis import Crisis
from repositories import CrisisRepository
from schemas.pagination import Page, PaginationParams, pagination_params
from services.audit_service import audit_event
from services.crisis import CrisisService


router = APIRouter(prefix="/crises", tags=["crises"])

# Reads are PUBLIC — visualizar a operação não exige token; isso facilita o
# painel público de transparência. Writes ficam restritos a dev + crisis_manager.
_WriteDep = Annotated[CurrentUser, Depends(require_role("dev", "crisis_manager"))]
_SessionDep = Annotated[Session, Depends(get_session)]
_PaginationDep = Annotated[PaginationParams, Depends(pagination_params)]


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


@router.get("", response_model=Page[CrisisListItemResponse])
def list_crises(
    session: _SessionDep,
    pagination: _PaginationDep,
    status: Annotated[CrisisStatus | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    type_: Annotated[CrisisType | None, Query(alias="type")] = None,
) -> Page[CrisisListItemResponse]:
    service = CrisisService(CrisisRepository(session))
    return service.list_crises(
        pagination,
        status=status,
        state=state,
        type_=type_,
    )


@router.get(
    "/{crisis_id}",
    response_model=CrisisDetailResponse,
    responses={404: {"description": "crisis not found"}},
)
def get_crisis(
    crisis_id: UUID,
    session: _SessionDep,
) -> CrisisDetailResponse:
    service = CrisisService(CrisisRepository(session))
    return service.get_crisis_detail(crisis_id)


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
