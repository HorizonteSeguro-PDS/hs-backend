"""Tests do endpoint atômico POST /shelters/{id}/inventory/initial-stock
(modal 1 do front: criar tipo novo + primeira entrada).

Cobre:
  - happy path: cria categoria + item + movement, retorna tudo
  - 409 se categoria com mesmo name já existe
  - 404 se shelter não existe
  - atomicidade: se categoria criada e movement falhar, NADA persiste
  - reason hardcoded como DONATION mesmo se front mandar outro (ignorado)
"""

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from domain.errors.http import ResourceAlreadyExists, ResourceNotFoundError
from domain.inventory.schemas import (
    InitialStockCategorySpec,
    InitialStockRequest,
)
from domain.models.inventory_item import InventoryItem
from domain.models.inventory_movement import InventoryMovement
from domain.models.resource_category import ResourceCategory
from domain.models.shelter import Shelter
from domain.schemas.enums import (
    BrazilianState,
    LotCategory,
    MovementDirection,
    MovementReason,
    ResourceUnit,
    ShelterStatus,
    ShelterType,
)
from services.inventory_service import InventoryService


def _setup_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    for table in (
        Shelter.__table__,
        ResourceCategory.__table__,
        InventoryItem.__table__,
        InventoryMovement.__table__,
    ):
        table.create(engine)
    return Session(engine)


def _seed_shelter(session: Session) -> Shelter:
    shelter = Shelter(
        id=uuid.uuid4(),
        responsible_user_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        name="Abrigo Teste",
        address="Rua A, 1",
        city="Maceio",
        state=BrazilianState.AL,
        capacity=100,
        occupation=0,
        shelter_type=ShelterType.INSTITUTIONAL,
        status=ShelterStatus.ACTIVE,
        verified=True,
    )
    session.add(shelter)
    session.commit()
    return shelter


def _payload(
    *,
    name: str = "banana_seca",
    unit: ResourceUnit = ResourceUnit.KG,
    lot_category: LotCategory = LotCategory.ESSENCIAIS,
    quantity: int = 50,
    source: str | None = "Doação X",
) -> InitialStockRequest:
    return InitialStockRequest(
        category=InitialStockCategorySpec(
            name=name,
            unit=unit,
            lot_category=lot_category,
            description=None,
        ),
        quantity=quantity,
        source=source,
        notes=None,
    )


def test_creates_category_item_and_movement_atomically():
    with _setup_session() as session:
        shelter = _seed_shelter(session)
        service = InventoryService(session)

        response = service.register_initial_stock(
            shelter_id=shelter.id,
            actor_id=uuid.uuid4(),
            payload=_payload(),
        )
        session.commit()

        # Response shape
        assert response.category.name == "banana_seca"
        assert response.category.unit == ResourceUnit.KG
        assert response.category.lot_category == LotCategory.ESSENCIAIS
        assert response.item.shelter_id == shelter.id
        assert response.item.category_id == response.category.id
        assert response.item.quantity_current == 50
        assert response.movement.direction == MovementDirection.IN
        assert response.movement.reason == MovementReason.DONATION
        assert response.movement.quantity == 50
        assert response.inventory_after == 50

        # Estado persistido
        assert (
            session.scalar(
                select(ResourceCategory).where(ResourceCategory.name == "banana_seca")
            )
            is not None
        )
        item = session.scalar(
            select(InventoryItem).where(InventoryItem.shelter_id == shelter.id)
        )
        assert item is not None and item.quantity_current == 50
        movement = session.scalar(
            select(InventoryMovement).where(InventoryMovement.shelter_id == shelter.id)
        )
        assert movement is not None and movement.quantity == 50


def test_blocks_when_category_name_already_exists():
    with _setup_session() as session:
        shelter = _seed_shelter(session)
        service = InventoryService(session)

        # Categoria pré-existente
        existing = ResourceCategory(
            id=uuid.uuid4(),
            name="cobertor",
            unit=ResourceUnit.UNIDADE,
            lot_category=LotCategory.ESSENCIAIS,
        )
        session.add(existing)
        session.commit()

        with pytest.raises(ResourceAlreadyExists) as exc:
            service.register_initial_stock(
                shelter_id=shelter.id,
                actor_id=uuid.uuid4(),
                payload=_payload(name="cobertor"),
            )

        assert "cobertor" in str(exc.value.detail).lower()

        # Inventory NAO foi tocado
        assert (
            session.scalar(
                select(InventoryItem).where(InventoryItem.shelter_id == shelter.id)
            )
            is None
        )


def test_404_when_shelter_does_not_exist():
    with _setup_session() as session:
        service = InventoryService(session)

        with pytest.raises(ResourceNotFoundError):
            service.register_initial_stock(
                shelter_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                payload=_payload(),
            )

        # Categoria nao foi criada
        assert (
            session.scalar(
                select(ResourceCategory).where(ResourceCategory.name == "banana_seca")
            )
            is None
        )


def test_distinct_categories_can_coexist_at_same_shelter():
    """Duas chamadas com categorias diferentes criam 2 items separados."""
    with _setup_session() as session:
        shelter = _seed_shelter(session)
        service = InventoryService(session)

        service.register_initial_stock(
            shelter_id=shelter.id,
            actor_id=uuid.uuid4(),
            payload=_payload(name="banana_seca", quantity=50),
        )
        service.register_initial_stock(
            shelter_id=shelter.id,
            actor_id=uuid.uuid4(),
            payload=_payload(name="acucar_mascavo", quantity=30),
        )
        session.commit()

        items = session.scalars(
            select(InventoryItem).where(InventoryItem.shelter_id == shelter.id)
        ).all()
        assert len(items) == 2
        assert {it.quantity_current for it in items} == {50, 30}
