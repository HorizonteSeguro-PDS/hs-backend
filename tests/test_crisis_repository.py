import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.models.crises_shelters import CrisesShelters
from domain.models.crisis import Crisis
from domain.models.shelter import Shelter
from domain.schemas.enums import BrazilianState, ShelterStatus, ShelterType
from repositories import CrisisRepository
from schemas.pagination import PaginationParams

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _create_tables(engine) -> None:
    for table in (Crisis.__table__, Shelter.__table__, CrisesShelters.__table__):
        table.create(engine)


def _make_crisis(
    name: str,
    *,
    status: CrisisStatus = CrisisStatus.ACTIVE,
    type_: CrisisType = CrisisType.FLOOD,
    state: BrazilianState = BrazilianState.SP,
    created_at: datetime = _NOW,
) -> Crisis:
    return Crisis(
        id=uuid.uuid4(),
        name=name,
        type=type_,
        status=status,
        state=state,
        city="Sao Paulo",
        severity_initial=3,
        created_by=uuid.uuid4(),
        created_at=created_at,
        updated_at=created_at,
    )


def _make_shelter(name: str) -> Shelter:
    return Shelter(
        id=uuid.uuid4(),
        responsible_user_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        name=name,
        address="Rua Principal, 100",
        city="Sao Paulo",
        state=BrazilianState.SP,
        capacity=100,
        occupation=25,
        shelter_type=ShelterType.INSTITUTIONAL,
        status=ShelterStatus.ACTIVE,
        verified=True,
    )


def test_list_paginated_returns_total_and_shelters_count():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        crisis_with_shelters = _make_crisis("Crise com abrigos")
        crisis_without_shelters = _make_crisis(
            "Crise sem abrigos",
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        shelter_one = _make_shelter("Abrigo 1")
        shelter_two = _make_shelter("Abrigo 2")
        crisis_with_shelters.shelters.extend([shelter_one, shelter_two])
        session.add_all([crisis_with_shelters, crisis_without_shelters])
        session.commit()

        rows, total = CrisisRepository(session).list_paginated(
            PaginationParams(page=1, size=10)
        )

        counts = {row.crisis.name: row.shelters_count for row in rows}
        assert total == 2
        assert rows[0].crisis.name == "Crise sem abrigos"
        assert counts["Crise com abrigos"] == 2
        assert counts["Crise sem abrigos"] == 0


def test_list_paginated_respects_pagination():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        session.add_all(
            [
                _make_crisis("Crise 1", created_at=datetime(2026, 1, 1)),
                _make_crisis("Crise 2", created_at=datetime(2026, 1, 2)),
                _make_crisis("Crise 3", created_at=datetime(2026, 1, 3)),
            ]
        )
        session.commit()

        rows, total = CrisisRepository(session).list_paginated(
            PaginationParams(page=2, size=1)
        )

        assert total == 3
        assert len(rows) == 1
        assert rows[0].crisis.name == "Crise 2"


def test_list_paginated_applies_filters_to_rows_and_total():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        session.add_all(
            [
                _make_crisis("SP ativa flood"),
                _make_crisis("RJ ativa flood", state=BrazilianState.RJ),
                _make_crisis("SP fechada flood", status=CrisisStatus.CLOSED),
                _make_crisis("SP ativa fire", type_=CrisisType.FIRE),
            ]
        )
        session.commit()

        rows, total = CrisisRepository(session).list_paginated(
            PaginationParams(page=1, size=10),
            status=CrisisStatus.ACTIVE,
            state=BrazilianState.SP,
            type_=CrisisType.FLOOD,
        )

        assert total == 1
        assert [row.crisis.name for row in rows] == ["SP ativa flood"]


def test_get_with_shelters_eager_loads_shelters():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        crisis = _make_crisis("Crise com abrigo")
        crisis.shelters.append(_make_shelter("Abrigo Central"))
        session.add(crisis)
        session.commit()

        saved = CrisisRepository(session).get_with_shelters(crisis.id)

        assert saved is not None
        assert len(saved.shelters) == 1
        assert saved.shelters[0].name == "Abrigo Central"
        assert CrisisRepository(session).get_with_shelters(uuid.uuid4()) is None
