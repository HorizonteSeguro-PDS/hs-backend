from uuid import UUID

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.crisis.schemas import (
    CrisisDetailResponse,
    CrisisListItemResponse,
)
from domain.errors.http import ResourceNotFoundError
from domain.models.crisis import Crisis
from domain.models.shelter import Shelter
from domain.schemas.enums import BrazilianState, SeverityLabel
from repositories import CrisisListRow, CrisisRepository
from schemas.pagination import PaginationParams
from services.base import BaseService


# --------------------------------------------------------------------------- #
# Severity helpers (regra de negocio no back)                                 #
# --------------------------------------------------------------------------- #

_SEVERITY_INT_TO_LABEL: dict[int, SeverityLabel] = {
    0: SeverityLabel.INATIVO,
    1: SeverityLabel.BAIXA,
    2: SeverityLabel.MEDIA,
    3: SeverityLabel.ALTA,
}


def severity_int_to_label(value: int | None) -> SeverityLabel:
    """Map the stored small-int severity to the label the frontend expects.

    Anything outside the 0-3 range — including NULL — degrades to INATIVO.
    """
    if value is None:
        return SeverityLabel.INATIVO
    return _SEVERITY_INT_TO_LABEL.get(value, SeverityLabel.INATIVO)


def derive_shelter_severity(occupation: int, capacity: int) -> SeverityLabel:
    """Derive shelter severity from occupation/capacity ratio.

    Thresholds:
        ratio == 0            -> INATIVO  (abrigo aberto mas sem gente)
        0   < ratio < 0.5     -> BAIXA
        0.5 <= ratio < 0.85   -> MÉDIA
        ratio >= 0.85         -> ALTA

    Defensive against capacity=0 (rare in seed but possible): returns INATIVO.
    """
    if capacity <= 0 or occupation <= 0:
        return SeverityLabel.INATIVO
    ratio = occupation / capacity
    if ratio < 0.5:
        return SeverityLabel.BAIXA
    if ratio < 0.85:
        return SeverityLabel.MEDIA
    return SeverityLabel.ALTA


def _crisis_severity_value(crisis: Crisis) -> int | None:
    """Prefer the calculated severity; fall back to the initial one."""
    if crisis.severity_calculated is not None:
        return crisis.severity_calculated
    return crisis.severity_initial


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
    ) -> list[CrisisListItemResponse]:
        """Return a flat list shaped for the frontend.

        The pagination wrapper was dropped on purpose (front nao quer
        envelope). `params` ainda controla offset/limit pra paginação no
        banco, mas o cliente só recebe o array.
        """
        rows, _ = self.repository.list_paginated(
            params,
            status=status,
            state=state,
            type_=type_,
        )
        return [self._list_item_from_row(row) for row in rows]

    def get_crisis_detail(self, crisis_id: UUID) -> CrisisDetailResponse:
        crisis = self.repository.get_with_shelters(crisis_id)
        if crisis is None:
            raise ResourceNotFoundError("crisis not found")

        shelters = list(crisis.shelters or [])
        return CrisisDetailResponse.model_validate(
            {
                "id": crisis.id,
                "name": crisis.name,
                "severity": severity_int_to_label(_crisis_severity_value(crisis)),
                "state": crisis.state,
                "city": crisis.city,
                "latitude": crisis.latitude,
                "longitude": crisis.longitude,
                "start_date": crisis.start_date,
                "shelters_count": len(shelters),
                "active": crisis.status == CrisisStatus.ACTIVE,
                "shelters": [self._shelter_payload(s) for s in shelters],
            }
        )

    def _list_item_from_row(self, row: CrisisListRow) -> CrisisListItemResponse:
        crisis = row.crisis
        return CrisisListItemResponse.model_validate(
            {
                "id": crisis.id,
                "name": crisis.name,
                "severity": severity_int_to_label(_crisis_severity_value(crisis)),
                "state": crisis.state,
                "city": crisis.city,
                "latitude": crisis.latitude,
                "longitude": crisis.longitude,
                "start_date": crisis.start_date,
                "shelters_count": row.shelters_count,
                "active": crisis.status == CrisisStatus.ACTIVE,
            }
        )

    @staticmethod
    def _shelter_payload(shelter: Shelter) -> dict:
        return {
            "id": shelter.id,
            "name": shelter.name,
            "city": shelter.city,
            "state": shelter.state,
            "longitude": shelter.longitude,
            "latitude": shelter.latitude,
            "urgent_needs": [],
            "capacity": shelter.capacity,
            "current_occupancy": shelter.occupation,
            "severity": derive_shelter_severity(shelter.occupation, shelter.capacity),
        }
