from uuid import UUID

from domain.models.shelter import Shelter
from domain.shelter.schemas import (
    ShelterCreateRequest,
    ShelterListItemResponse,
    ShelterRead,
    ShelterUpdateRequest,
)
from domain.schemas.enums import ShelterStatus
from repositories import ShelterRepository
from schemas.pagination import Page, PaginationParams
from services.base import BaseService


class ShelterService(BaseService[Shelter]):
    def __init__(self, repository: ShelterRepository) -> None:
        super().__init__(repository)
        self.repository = repository

    def list_shelters(
        self,
        params: PaginationParams,
    ) -> Page[ShelterListItemResponse]:
        items = self.repository.list(offset=params.offset, limit=params.limit)
        total = self.repository.count()
        return Page[ShelterListItemResponse].create(
            items=[ShelterListItemResponse.model_validate(item) for item in items],
            total=total,
            params=params,
        )

    def get_shelter(self, shelter_id: UUID) -> ShelterRead:
        return ShelterRead.model_validate(self.get_or_raise(shelter_id))

    def create_shelter(
        self,
        payload: ShelterCreateRequest,
        *,
        created_by: UUID,
    ) -> Shelter:
        shelter = Shelter(
            **payload.model_dump(),
            organization_id=None,
            responsible_user_id=created_by,
            created_by=created_by,
            verified_by=None,
            status=ShelterStatus.PREPARING,
            verified=False,
        )
        return self.create(shelter)

    def update_shelter(
        self, shelter_id: UUID, payload: ShelterUpdateRequest
    ) -> Shelter:
        return self.update(shelter_id, payload.model_dump(exclude_unset=True))

    def delete_shelter(self, shelter_id: UUID) -> None:
        self.delete(shelter_id)
