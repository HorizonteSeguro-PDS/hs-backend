"""Service do dashboard de gestor de abrigos.

Um unico metodo publico: `get_crisis_operations(crisis_id, viewer)`. Carrega
tudo em poucas queries, aplica scope por organization_id, e devolve o
CrisisOperationsResponse aninhado.

Scoping rules:
  - dev                            -> ve todos os shelters da crise
  - crisis_manager, shelter_manager-> ve so shelters da MESMA organization_id
                                       do viewer (se viewer.organization_id é
                                       None, devolve lista vazia de shelters)
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from domain.auth.enums import Role
from domain.auth.jwt import CurrentUser
from domain.crisis.enums import CrisisStatus
from domain.errors.http import ResourceNotFoundError
from domain.models.beneficiary import Beneficiary
from domain.models.crisis import Crisis
from domain.models.inventory_item import InventoryItem
from domain.models.inventory_movement import InventoryMovement
from domain.models.resource_category import ResourceCategory
from domain.models.shelter import Shelter
from domain.models.shelter_stay import ShelterStay
from domain.models.users_shelters import UsersShelters
from domain.operations.schemas import (
    CrisisOperationsResponse,
    PersonResponse,
    ResourceMovementResponse,
    ShelterOperationsResponse,
    SupplyResponse,
)
from domain.schemas.enums import SeverityLabel, SupplyStatus
from services.crisis import derive_shelter_severity


# Thresholds da escada Sufficient/Low/Critical.
_LOW_RATIO = 0.5
_CRITICAL_RATIO = 0.2


def derive_supply_status(current: int, maximum: int | None) -> SupplyStatus:
    """Map (current, max) to a SupplyStatus label.

    Sem teto definido (max=NULL) → sempre Sufficient: nao tem como alarmar
    se a gente nao sabe quanto é "cheio".

    Regra:
        ratio = current / max
        ratio >= 0.5            -> Sufficient
        0.2 <= ratio < 0.5      -> Low
        ratio < 0.2             -> Critical
    """
    if maximum is None or maximum <= 0:
        return SupplyStatus.SUFFICIENT
    if current <= 0:
        return SupplyStatus.CRITICAL
    ratio = current / maximum
    if ratio >= _LOW_RATIO:
        return SupplyStatus.SUFFICIENT
    if ratio >= _CRITICAL_RATIO:
        return SupplyStatus.LOW
    return SupplyStatus.CRITICAL


def _is_org_scoped(viewer: CurrentUser) -> bool:
    """Viewer cai na regra de scope-por-org se NAO for dev."""
    return Role.DEV not in viewer.roles


def _relative_occupation(occupation: int, capacity: int) -> float:
    if capacity <= 0:
        return 0.0
    return occupation / capacity


def _crisis_severity_value(crisis: Crisis) -> int | None:
    if crisis.severity_calculated is not None:
        return crisis.severity_calculated
    return crisis.severity_initial


class OperationsService:
    """Encapsula a leitura do dashboard.

    Nao herda BaseService porque a operacao é uma agregacao read-only que
    nao bate com CRUD de uma entidade so.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_crisis_operations(
        self, crisis_id: UUID, viewer: CurrentUser
    ) -> CrisisOperationsResponse:
        crisis = self.session.scalar(
            select(Crisis)
            .options(selectinload(Crisis.shelters))
            .where(Crisis.id == crisis_id)
        )
        if crisis is None:
            raise ResourceNotFoundError("crisis not found")

        shelters = self._filter_shelters_for_viewer(list(crisis.shelters), viewer)
        shelter_ids = [s.id for s in shelters]

        # Pré-carrega tudo que depende dos shelter_ids em uma query por
        # tabela. Evita N+1 em loops de abrigos.
        supplies_by_shelter = self._load_supplies(shelter_ids)
        movements_by_shelter = self._load_movements(shelter_ids)
        people_by_shelter = self._load_people(shelter_ids)
        managers_by_shelter = self._load_active_manager_counts(shelter_ids)
        shelter_name_lookup = {s.id: s.name for s in shelters}

        return CrisisOperationsResponse(
            id=crisis.id,
            name=crisis.name,
            city=crisis.city,
            shelters=[
                self._build_shelter_block(
                    shelter,
                    supplies=supplies_by_shelter.get(shelter.id, []),
                    movements=movements_by_shelter.get(shelter.id, []),
                    people=people_by_shelter.get(shelter.id, []),
                    active_managers=managers_by_shelter.get(shelter.id, 0),
                    shelter_name_lookup=shelter_name_lookup,
                )
                for shelter in shelters
            ],
        )

    # ------------------------------------------------------------------ #
    # Scoping                                                            #
    # ------------------------------------------------------------------ #

    def _filter_shelters_for_viewer(
        self, shelters: list[Shelter], viewer: CurrentUser
    ) -> list[Shelter]:
        """Dev vê tudo; demais roles ficam restritos à propria organization_id.

        Se o viewer nao tem organization_id (e nao é dev), ele nao vê NADA —
        retorna lista vazia. Isso evita vazamento acidental.
        """
        if not _is_org_scoped(viewer):
            return shelters
        if viewer.organization_id is None:
            return []
        return [s for s in shelters if s.organization_id == viewer.organization_id]

    # ------------------------------------------------------------------ #
    # Per-shelter aggregation                                            #
    # ------------------------------------------------------------------ #

    def _build_shelter_block(
        self,
        shelter: Shelter,
        *,
        supplies: list[tuple[InventoryItem, ResourceCategory]],
        movements: list[tuple[InventoryMovement, ResourceCategory]],
        people: list[tuple[Beneficiary, ShelterStay]],
        active_managers: int,
        shelter_name_lookup: dict[UUID, str],
    ) -> ShelterOperationsResponse:
        severity = self._shelter_severity(shelter)
        return ShelterOperationsResponse(
            id=shelter.id,
            name=shelter.name,
            city=shelter.city,
            state=shelter.state,
            severity=severity,
            capacity=shelter.capacity,
            current_occupancy=shelter.occupation,
            relative_occupation=_relative_occupation(
                shelter.occupation, shelter.capacity
            ),
            active_managers=active_managers,
            supplies=[
                SupplyResponse(
                    name=category.name,
                    current_quantity=item.quantity_current,
                    unit=category.unit,
                    max_capacity=item.quantity_max,
                    status=derive_supply_status(
                        item.quantity_current, item.quantity_max
                    ),
                    lot_category=category.lot_category,
                )
                for item, category in supplies
            ],
            resources=[
                ResourceMovementResponse(
                    created_at=movement.created_at,
                    type=movement.direction,
                    category=category.lot_category,
                    name=category.name,
                    quantity=movement.quantity,
                    unit=category.unit,
                    destined_to=(
                        shelter_name_lookup.get(movement.destination_shelter_id)
                        if movement.destination_shelter_id is not None
                        else None
                    ),
                )
                for movement, category in movements
            ],
            people=[
                PersonResponse(
                    name=beneficiary.name,
                    age=beneficiary.age,
                    vulnerabilities=beneficiary.vulnerability,
                    cpf=beneficiary.cpf,
                )
                for beneficiary, _stay in people
            ],
        )

    @staticmethod
    def _shelter_severity(shelter: Shelter) -> SeverityLabel:
        return derive_shelter_severity(shelter.occupation, shelter.capacity)

    # ------------------------------------------------------------------ #
    # Bulk loaders (1 query per relation, grouped in Python)             #
    # ------------------------------------------------------------------ #

    def _load_supplies(
        self, shelter_ids: list[UUID]
    ) -> dict[UUID, list[tuple[InventoryItem, ResourceCategory]]]:
        if not shelter_ids:
            return {}
        rows = self.session.execute(
            select(InventoryItem, ResourceCategory)
            .join(ResourceCategory, ResourceCategory.id == InventoryItem.category_id)
            .where(InventoryItem.shelter_id.in_(shelter_ids))
            .order_by(ResourceCategory.name)
        ).all()
        out: dict[UUID, list[tuple[InventoryItem, ResourceCategory]]] = {}
        for item, category in rows:
            out.setdefault(item.shelter_id, []).append((item, category))
        return out

    def _load_movements(
        self, shelter_ids: list[UUID]
    ) -> dict[UUID, list[tuple[InventoryMovement, ResourceCategory]]]:
        if not shelter_ids:
            return {}
        rows = self.session.execute(
            select(InventoryMovement, ResourceCategory)
            .join(
                ResourceCategory,
                ResourceCategory.id == InventoryMovement.category_id,
            )
            .where(InventoryMovement.shelter_id.in_(shelter_ids))
            .order_by(InventoryMovement.created_at.desc())
        ).all()
        out: dict[UUID, list[tuple[InventoryMovement, ResourceCategory]]] = {}
        for movement, category in rows:
            out.setdefault(movement.shelter_id, []).append((movement, category))
        return out

    def _load_people(
        self, shelter_ids: list[UUID]
    ) -> dict[UUID, list[tuple[Beneficiary, ShelterStay]]]:
        """Beneficiários com stay aberto (checked_out_at IS NULL) em cada abrigo."""
        if not shelter_ids:
            return {}
        rows = self.session.execute(
            select(Beneficiary, ShelterStay)
            .join(ShelterStay, ShelterStay.beneficiary_id == Beneficiary.id)
            .where(
                ShelterStay.shelter_id.in_(shelter_ids),
                ShelterStay.checked_out_at.is_(None),
            )
            .order_by(Beneficiary.name)
        ).all()
        out: dict[UUID, list[tuple[Beneficiary, ShelterStay]]] = {}
        for beneficiary, stay in rows:
            out.setdefault(stay.shelter_id, []).append((beneficiary, stay))
        return out

    def _load_active_manager_counts(self, shelter_ids: list[UUID]) -> dict[UUID, int]:
        """Conta linhas em users_shelters por shelter — i.e., managers com escopo."""
        if not shelter_ids:
            return {}
        rows = self.session.execute(
            select(UsersShelters.shelter_id, func.count(UsersShelters.user_id))
            .where(UsersShelters.shelter_id.in_(shelter_ids))
            .group_by(UsersShelters.shelter_id)
        ).all()
        return {shelter_id: int(count) for shelter_id, count in rows}


__all__ = [
    "OperationsService",
    "derive_supply_status",
    # re-expose for tests that target the active rule
    "CrisisStatus",
]
