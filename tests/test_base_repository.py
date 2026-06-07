import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.models.crises_shelters import CrisesShelters
from domain.models.crisis import Crisis
from domain.models.shelter import Shelter
from domain.schemas.enums import BrazilianState
from repositories import BaseRepository


def _make_crisis(name: str) -> Crisis:
    return Crisis(
        id=uuid.uuid4(),
        name=name,
        type=CrisisType.FLOOD,
        status=CrisisStatus.ACTIVE,
        state=BrazilianState.SP,
        city="Sao Paulo",
        created_by=uuid.uuid4(),
    )


def test_base_repository_crud_helpers_without_commit():
    engine = create_engine("sqlite:///:memory:")
    for table in (Crisis.__table__, Shelter.__table__, CrisesShelters.__table__):
        table.create(engine)

    with Session(engine) as session:
        repository = BaseRepository(session, Crisis)
        crisis = _make_crisis("Enchente Teste")

        assert repository.add(crisis) is crisis
        repository.flush()
        repository.refresh(crisis)

        assert repository.get(crisis.id) == crisis
        assert repository.get(uuid.uuid4()) is None
        assert repository.count() == 1

        repository.delete(crisis)
        repository.flush()

        assert repository.get(crisis.id) is None
        assert repository.count() == 0


def test_base_repository_list_respects_offset_and_limit():
    engine = create_engine("sqlite:///:memory:")
    for table in (Crisis.__table__, Shelter.__table__, CrisesShelters.__table__):
        table.create(engine)

    with Session(engine) as session:
        repository = BaseRepository(session, Crisis)
        for crisis in [
            _make_crisis("Crise 1"),
            _make_crisis("Crise 2"),
            _make_crisis("Crise 3"),
        ]:
            repository.add(crisis)
        repository.flush()

        assert len(repository.list()) == 3
        assert len(repository.list(offset=1)) == 2
        assert len(repository.list(offset=1, limit=1)) == 1
