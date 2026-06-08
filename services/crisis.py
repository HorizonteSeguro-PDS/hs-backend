from uuid import UUID

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.crisis.schemas import CrisisDetailResponse, CrisisListItemResponse
from domain.errors.http import ResourceNotFoundError
from domain.models.crisis import Crisis
from domain.schemas.enums import BrazilianState
from repositories import CrisisListRow, CrisisRepository
from schemas.pagination import Page, PaginationParams
from services.base import BaseService


class CrisisService(BaseService[Crisis]):
    def __init__(self, repository: CrisisRepository) -> None:
        super().__init__(repository)
        self.repository = repository

    def list_crises(
        self,
        params: PaginationParams,
        *,
        status: CrisisStatus | None = None,
        state: BrazilianState | str | None = None,
        type_: CrisisType | None = None,
    ) -> Page[CrisisListItemResponse]:
        rows, total = self.repository.list_paginated(
            params,
            status=status,
            state=state,
            type_=type_,
        )
        return Page[CrisisListItemResponse].create(
            items=[self._list_item_from_row(row) for row in rows],
            total=total,
            params=params,
        )

    def get_crisis_detail(self, crisis_id: UUID) -> CrisisDetailResponse:
        crisis = self.repository.get_with_shelters(crisis_id)
        if crisis is None:
            raise ResourceNotFoundError("crisis not found")
        return CrisisDetailResponse.model_validate(crisis)

    def _list_item_from_row(self, row: CrisisListRow) -> CrisisListItemResponse:
        return CrisisListItemResponse.model_validate(
            {
                "id": row.crisis.id,
                "organization_id": row.crisis.organization_id,
                "name": row.crisis.name,
                "type": row.crisis.type,
                "status": row.crisis.status,
                "state": row.crisis.state,
                "city": row.crisis.city,
                "start_date": row.crisis.start_date,
                "severity_initial": row.crisis.severity_initial,
                "severity_calculated": row.crisis.severity_calculated,
                "created_at": row.crisis.created_at,
                "shelters_count": row.shelters_count,
            }
        )
