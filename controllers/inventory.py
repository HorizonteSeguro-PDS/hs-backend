from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.inventory.schemas import (
    InitialStockRequest,
    InitialStockResponse,
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
    """Registra entrada ou saída de recurso EXISTENTE (modal 2).

    `reason` é opcional: default `donation` se IN, `distribution` se OUT.
    """
    result = InventoryService(session).record_movement(
        shelter_id=shelter_id,
        actor_id=user.id,
        payload=payload,
    )
    session.commit()
    return result


@router.post(
    "/{shelter_id}/inventory/initial-stock",
    response_model=InitialStockResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"description": "shelter not found"},
        409: {"description": "resource category with that name already exists"},
    },
)
def register_initial_stock(
    shelter_id: UUID,
    payload: InitialStockRequest,
    session: _SessionDep,
    user: _AnyAuth,
) -> InitialStockResponse:
    """Cria um TIPO de recurso novo + grava a primeira entrada (modal 1).

    Atômico: se a criação da categoria ou o movement falhar, nada persiste.
    Reason do movement é `donation` por default.
    """
    result = InventoryService(session).register_initial_stock(
        shelter_id=shelter_id,
        actor_id=user.id,
        payload=payload,
    )
    session.commit()
    return result
