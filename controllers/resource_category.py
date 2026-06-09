from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.inventory.schemas import (
    ResourceCategoryCreateRequest,
    ResourceCategoryRead,
    ResourceCategoryUpdateRequest,
)
from domain.schemas.enums import LotCategory
from repositories import ResourceCategoryRepository
from services import ResourceCategoryService


router = APIRouter(prefix="/resource-categories", tags=["resource-categories"])

_WriteDep = Annotated[CurrentUser, Depends(require_role("dev", "crisis_manager"))]
_SessionDep = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[ResourceCategoryRead])
def list_categories(
    session: _SessionDep,
    lot_category: Annotated[LotCategory | None, Query()] = None,
) -> list[ResourceCategoryRead]:
    """Lista todas as categorias, ou filtra por `lot_category` se fornecido.

    Usado pelos modais de inflow/outflow do front pra popular o dropdown de
    "tipo de recurso" depois do gestor escolher o grupo (Essenciais / Saude /
    etc).
    """
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    if lot_category is not None:
        return service.list_by_lot_category(lot_category)
    return service.list_all()


@router.get("/search", response_model=list[ResourceCategoryRead])
def search_categories(
    session: _SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[ResourceCategoryRead]:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    return service.search(q, limit=limit)


@router.get("/{category_id}", response_model=ResourceCategoryRead)
def get_category(
    category_id: UUID,
    session: _SessionDep,
) -> ResourceCategoryRead:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    return service.get(category_id)


@router.post(
    "",
    response_model=ResourceCategoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: ResourceCategoryCreateRequest,
    session: _SessionDep,
    _user: _WriteDep,
) -> ResourceCategoryRead:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    category = service.create(payload)
    session.commit()
    return category


@router.patch("/{category_id}", response_model=ResourceCategoryRead)
def update_category(
    category_id: UUID,
    payload: ResourceCategoryUpdateRequest,
    session: _SessionDep,
    _user: _WriteDep,
) -> ResourceCategoryRead:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    category = service.update(category_id, payload)
    session.commit()
    return category
