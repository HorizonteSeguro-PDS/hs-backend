from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.inventory.schemas import (
    InventoryItemRead,
    InventoryMovementCreateRequest,
    InventoryMovementRead,
    InventoryMovementRecordedResponse,
)
from domain.schemas.enums import MovementReason
from schemas.pagination import Page, PaginationParams, pagination_params
from services import InventoryService


router = APIRouter(prefix="/shelters", tags=["inventory"])

_AnyAuth = Annotated[
    CurrentUser,
    Depends(require_role("dev", "crisis_manager", "shelter_manager")),
]
_SessionDep = Annotated[Session, Depends(get_session)]


@router.get(
    "/{shelter_id}/inventory",
    response_model=list[InventoryItemRead],
)
def list_inventory(
    shelter_id: UUID,
    session: _SessionDep,
    _user: _AnyAuth,
) -> list[InventoryItemRead]:
    return InventoryService(session).list_inventory_for_shelter(shelter_id=shelter_id)


@router.get(
    "/{shelter_id}/inventory/movements",
    response_model=Page[InventoryMovementRead],
)
def list_movements(
    shelter_id: UUID,
    session: _SessionDep,
    _user: _AnyAuth,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    category_id: Annotated[UUID | None, Query()] = None,
    reason: Annotated[MovementReason | None, Query()] = None,
) -> Page[InventoryMovementRead]:
    return InventoryService(session).list_movements_for_shelter(
        pagination,
        shelter_id=shelter_id,
        category_id=category_id,
        reason=reason,
    )


@router.post(
    "/{shelter_id}/inventory/movements",
    response_model=InventoryMovementRecordedResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_movement(
    shelter_id: UUID,
    payload: InventoryMovementCreateRequest,
    session: _SessionDep,
    user: _AnyAuth,
) -> InventoryMovementRecordedResponse:
    result = InventoryService(session).record_movement(
        shelter_id=shelter_id,
        actor_id=user.id,
        payload=payload,
    )
    session.commit()
    return result
