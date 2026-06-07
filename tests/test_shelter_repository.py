import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.models.crises_shelters import CrisesShelters
from domain.models.crisis import Crisis
from domain.models.shelter import Shelter
from domain.schemas.enums import BrazilianState, ShelterStatus, ShelterType
from repositories import ShelterRepository


def _create_tables(engine) -> None:
    for table in (Crisis.__table__, Shelter.__table__, CrisesShelters.__table__):
        table.create(engine)


def _make_crisis() -> Crisis:
    return Crisis(
        id=uuid.uuid4(),
        name="Enchente Teste",
        type=CrisisType.FLOOD,
        status=CrisisStatus.ACTIVE,
        state=BrazilianState.SP,
        city="Sao Paulo",
        created_by=uuid.uuid4(),
    )


def _make_shelter(name: str) -> Shelter:
    return Shelter(
        id=uuid.uuid4(),
        responsible_user_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        name=name,
        address="Rua Principal, 100",
        capacity=100,
        occupation=20,
        shelter_type=ShelterType.INSTITUTIONAL,
        status=ShelterStatus.ACTIVE,
        verified=True,
    )


def test_shelter_repository_crud_helpers_without_commit():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        repository = ShelterRepository(session)
        shelter = _make_shelter("Abrigo Central")

        assert repository.add(shelter) is shelter
        repository.flush()

        assert repository.get(shelter.id) == shelter
        assert repository.get(uuid.uuid4()) is None
        assert repository.count() == 1

        repository.delete(shelter)
        repository.flush()

        assert repository.get(shelter.id) is None
        assert repository.count() == 0


def test_shelter_repository_list_respects_pagination_and_m2m_relationship():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        repository = ShelterRepository(session)
        crisis = _make_crisis()
        shelters = [
            _make_shelter("Abrigo 1"),
            _make_shelter("Abrigo 2"),
            _make_shelter("Abrigo 3"),
        ]
        crisis.shelters.append(shelters[0])
        session.add(crisis)
        for shelter in shelters[1:]:
            repository.add(shelter)
        repository.flush()

        assert len(repository.list()) == 3
        assert len(repository.list(offset=1)) == 2
        assert len(repository.list(offset=1, limit=1)) == 1
        assert shelters[0].crises == [crisis]
