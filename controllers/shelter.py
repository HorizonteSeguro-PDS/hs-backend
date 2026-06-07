from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.shelter.schemas import (
    ShelterCreateRequest,
    ShelterListItemResponse,
    ShelterRead,
    ShelterUpdateRequest,
)
from repositories import ShelterRepository
from schemas.pagination import Page, PaginationParams, pagination_params
from services.shelter import ShelterService


router = APIRouter(prefix="/shelters", tags=["shelters"])

_ReadDep = Annotated[
    CurrentUser,
    Depends(require_role("dev", "crisis_manager", "shelter_manager", "sheltered")),
]
_WriteDep = Annotated[CurrentUser, Depends(require_role("dev", "shelter_manager"))]
_SessionDep = Annotated[Session, Depends(get_session)]
_PaginationDep = Annotated[PaginationParams, Depends(pagination_params)]


@router.get("", response_model=Page[ShelterListItemResponse])
def list_shelters(
    session: _SessionDep,
    _user: _ReadDep,
    pagination: _PaginationDep,
) -> Page[ShelterListItemResponse]:
    service = ShelterService(ShelterRepository(session))
    return service.list_shelters(pagination)


@router.get(
    "/{shelter_id}",
    response_model=ShelterRead,
    responses={404: {"description": "shelter not found"}},
)
def get_shelter(
    shelter_id: UUID,
    session: _SessionDep,
    _user: _ReadDep,
) -> ShelterRead:
    service = ShelterService(ShelterRepository(session))
    return service.get_shelter(shelter_id)


@router.post("", response_model=ShelterRead, status_code=status.HTTP_201_CREATED)
def create_shelter(
    payload: ShelterCreateRequest,
    session: _SessionDep,
    user: _WriteDep,
) -> ShelterRead:
    service = ShelterService(ShelterRepository(session))
    shelter = service.create_shelter(payload, created_by=user.id)
    session.commit()
    session.refresh(shelter)
    return shelter


@router.patch(
    "/{shelter_id}",
    response_model=ShelterRead,
    responses={404: {"description": "shelter not found"}},
)
def update_shelter(
    shelter_id: UUID,
    payload: ShelterUpdateRequest,
    session: _SessionDep,
    _user: _WriteDep,
) -> ShelterRead:
    service = ShelterService(ShelterRepository(session))
    shelter = service.update_shelter(shelter_id, payload)
    session.commit()
    session.refresh(shelter)
    return shelter


@router.delete(
    "/{shelter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "shelter not found"}},
)
def delete_shelter(
    shelter_id: UUID,
    session: _SessionDep,
    _user: _WriteDep,
) -> Response:
    service = ShelterService(ShelterRepository(session))
    service.delete_shelter(shelter_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
