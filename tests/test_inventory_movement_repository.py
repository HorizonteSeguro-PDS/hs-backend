import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.models.inventory_movement import InventoryMovement
from domain.schemas.enums import MovementDirection, MovementReason
from repositories import InventoryMovementRepository
from schemas.pagination import PaginationParams


def _create_tables(engine) -> None:
    InventoryMovement.__table__.create(engine)


def _make_movement(
    shelter_id: uuid.UUID,
    category_id: uuid.UUID,
    *,
    direction: MovementDirection = MovementDirection.IN,
    quantity: int = 10,
    reason: MovementReason = MovementReason.DONATION,
    created_at: datetime | None = None,
) -> InventoryMovement:
    m = InventoryMovement(
        id=uuid.uuid4(),
        shelter_id=shelter_id,
        category_id=category_id,
        direction=direction,
        quantity=quantity,
        reason=reason,
        source=None,
        notes=None,
        created_by=uuid.uuid4(),
    )
    if created_at is not None:
        m.created_at = created_at
    else:
        m.created_at = datetime.now(timezone.utc)
    return m


def test_list_paginated_for_shelter_returns_total_and_rows():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    shelter_a = uuid.uuid4()
    shelter_b = uuid.uuid4()
    category = uuid.uuid4()

    with Session(engine) as session:
        for _ in range(5):
            session.add(_make_movement(shelter_a, category))
        for _ in range(2):
            session.add(_make_movement(shelter_b, category))
        session.commit()

        repo = InventoryMovementRepository(session)
        rows, total = repo.list_paginated_for_shelter(
            PaginationParams(page=1, size=10), shelter_id=shelter_a
        )
        assert total == 5
        assert len(rows) == 5
        assert all(r.shelter_id == shelter_a for r in rows)


def test_list_paginated_filters_by_category_and_reason():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    shelter = uuid.uuid4()
    cat_a = uuid.uuid4()
    cat_b = uuid.uuid4()

    with Session(engine) as session:
        session.add(_make_movement(shelter, cat_a, reason=MovementReason.DONATION))
        session.add(_make_movement(shelter, cat_a, reason=MovementReason.DISTRIBUTION))
        session.add(_make_movement(shelter, cat_b, reason=MovementReason.DONATION))
        session.commit()

        repo = InventoryMovementRepository(session)

        # filter by category
        _, total = repo.list_paginated_for_shelter(
            PaginationParams(page=1, size=10),
            shelter_id=shelter,
            category_id=cat_a,
        )
        assert total == 2

        # filter by reason
        _, total = repo.list_paginated_for_shelter(
            PaginationParams(page=1, size=10),
            shelter_id=shelter,
            reason=MovementReason.DONATION,
        )
        assert total == 2

        # filter by both
        _, total = repo.list_paginated_for_shelter(
            PaginationParams(page=1, size=10),
            shelter_id=shelter,
            category_id=cat_a,
            reason=MovementReason.DONATION,
        )
        assert total == 1


def test_list_paginated_orders_by_created_at_desc():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    shelter = uuid.uuid4()
    category = uuid.uuid4()

    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    middle = datetime(2026, 6, 1, tzinfo=timezone.utc)
    new = datetime(2026, 12, 1, tzinfo=timezone.utc)

    with Session(engine) as session:
        session.add(_make_movement(shelter, category, created_at=middle))
        session.add(_make_movement(shelter, category, created_at=old))
        session.add(_make_movement(shelter, category, created_at=new))
        session.commit()

        repo = InventoryMovementRepository(session)
        rows, _ = repo.list_paginated_for_shelter(
            PaginationParams(page=1, size=10), shelter_id=shelter
        )
        # Convert to naive datetime for comparison (since SQLite returns naive)
        expected = [new.replace(tzinfo=None), middle.replace(tzinfo=None), old.replace(tzinfo=None)]
        assert [r.created_at.replace(tzinfo=None) if r.created_at.tzinfo else r.created_at for r in rows] == expected