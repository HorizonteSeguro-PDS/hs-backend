"""Tests for InventoryService.record_movement — the atomic write of
(movement row + inventory_items cache update), with negative-balance refusal.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.inventory.schemas import InventoryMovementCreateRequest
from domain.models.inventory_item import InventoryItem
from domain.models.inventory_movement import InventoryMovement
from domain.models.resource_category import ResourceCategory
from domain.schemas.enums import (
    LotCategory,
    MovementDirection,
    MovementReason,
    ResourceUnit,
)
from services.inventory_service import (
    InsufficientInventoryError,
    InventoryService,
)


def _setup_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    for table in (
        ResourceCategory.__table__,
        InventoryItem.__table__,
        InventoryMovement.__table__,
    ):
        table.create(engine)
    return Session(engine)


def _seed_category(session: Session, name: str = "cobertor") -> ResourceCategory:
    cat = ResourceCategory(
        id=uuid.uuid4(),
        name=name,
        unit=ResourceUnit.UNIDADE,
        lot_category=LotCategory.BEDDING,
        description=None,
    )
    session.add(cat)
    session.commit()
    return cat


def _payload(
    category_id: uuid.UUID,
    *,
    direction: MovementDirection,
    quantity: int,
    reason: MovementReason = MovementReason.DONATION,
) -> InventoryMovementCreateRequest:
    return InventoryMovementCreateRequest(
        category_id=category_id,
        direction=direction,
        quantity=quantity,
        reason=reason,
        source="Test source",
        notes=None,
    )


class TestRecordMovementIn:
    def test_first_in_creates_inventory_item_and_movement(self):
        with _setup_session() as session:
            cat = _seed_category(session)
            shelter_id = uuid.uuid4()
            actor_id = uuid.uuid4()

            service = InventoryService(session)
            result = service.record_movement(
                shelter_id=shelter_id,
                actor_id=actor_id,
                payload=_payload(cat.id, direction=MovementDirection.IN, quantity=50),
            )
            session.commit()

            assert result.inventory_after == 50
            assert result.movement.quantity == 50
            assert result.movement.direction == MovementDirection.IN

            # cache populated
            item = session.query(InventoryItem).one()
            assert item.shelter_id == shelter_id
            assert item.category_id == cat.id
            assert item.quantity_current == 50

            # history recorded
            mv = session.query(InventoryMovement).one()
            assert mv.shelter_id == shelter_id
            assert mv.created_by == actor_id

    def test_second_in_increments_cache(self):
        with _setup_session() as session:
            cat = _seed_category(session)
            shelter_id = uuid.uuid4()

            service = InventoryService(session)
            service.record_movement(
                shelter_id=shelter_id,
                actor_id=uuid.uuid4(),
                payload=_payload(cat.id, direction=MovementDirection.IN, quantity=30),
            )
            session.commit()

            result = service.record_movement(
                shelter_id=shelter_id,
                actor_id=uuid.uuid4(),
                payload=_payload(cat.id, direction=MovementDirection.IN, quantity=20),
            )
            session.commit()

            assert result.inventory_after == 50
            assert session.query(InventoryItem).count() == 1
            assert session.query(InventoryMovement).count() == 2


class TestRecordMovementOut:
    def test_out_with_sufficient_stock_decrements_cache(self):
        with _setup_session() as session:
            cat = _seed_category(session)
            shelter_id = uuid.uuid4()

            service = InventoryService(session)
            service.record_movement(
                shelter_id=shelter_id,
                actor_id=uuid.uuid4(),
                payload=_payload(cat.id, direction=MovementDirection.IN, quantity=100),
            )
            session.commit()

            result = service.record_movement(
                shelter_id=shelter_id,
                actor_id=uuid.uuid4(),
                payload=_payload(
                    cat.id,
                    direction=MovementDirection.OUT,
                    quantity=30,
                    reason=MovementReason.DISTRIBUTION,
                ),
            )
            session.commit()

            assert result.inventory_after == 70

    def test_out_when_balance_would_go_negative_raises_400(self):
        with _setup_session() as session:
            cat = _seed_category(session)
            shelter_id = uuid.uuid4()

            service = InventoryService(session)
            service.record_movement(
                shelter_id=shelter_id,
                actor_id=uuid.uuid4(),
                payload=_payload(cat.id, direction=MovementDirection.IN, quantity=10),
            )
            session.commit()

            with pytest.raises(InsufficientInventoryError) as exc:
                service.record_movement(
                    shelter_id=shelter_id,
                    actor_id=uuid.uuid4(),
                    payload=_payload(
                        cat.id,
                        direction=MovementDirection.OUT,
                        quantity=20,
                        reason=MovementReason.DISTRIBUTION,
                    ),
                )
            assert exc.value.status_code == 400
            assert exc.value.detail["error"] == "insufficient_inventory"
            assert exc.value.detail["requested"] == 20
            assert exc.value.detail["available"] == 10

    def test_out_on_empty_inventory_raises_400(self):
        """First-ever movement is OUT — should refuse since there's nothing in cache."""
        with _setup_session() as session:
            cat = _seed_category(session)

            service = InventoryService(session)
            with pytest.raises(InsufficientInventoryError):
                service.record_movement(
                    shelter_id=uuid.uuid4(),
                    actor_id=uuid.uuid4(),
                    payload=_payload(
                        cat.id,
                        direction=MovementDirection.OUT,
                        quantity=1,
                        reason=MovementReason.DISTRIBUTION,
                    ),
                )


class TestListing:
    def test_list_inventory_for_shelter_returns_snapshot(self):
        with _setup_session() as session:
            cat_a = _seed_category(session, "cobertor")
            cat_b = _seed_category(session, "agua_potavel")
            shelter_id = uuid.uuid4()

            service = InventoryService(session)
            service.record_movement(
                shelter_id=shelter_id,
                actor_id=uuid.uuid4(),
                payload=_payload(cat_a.id, direction=MovementDirection.IN, quantity=10),
            )
            service.record_movement(
                shelter_id=shelter_id,
                actor_id=uuid.uuid4(),
                payload=_payload(
                    cat_b.id, direction=MovementDirection.IN, quantity=200
                ),
            )
            session.commit()

            inventory = service.list_inventory_for_shelter(shelter_id=shelter_id)
            assert len(inventory) == 2
            quantities = {it.category_id: it.quantity_current for it in inventory}
            assert quantities[cat_a.id] == 10
            assert quantities[cat_b.id] == 200
