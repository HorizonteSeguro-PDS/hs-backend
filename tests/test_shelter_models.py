import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.models.crises_shelters import CrisesShelters
from domain.models.crisis import Crisis
from domain.models.shelter import Shelter
from domain.schemas.enums import BrazilianState, ShelterStatus, ShelterType


def test_crisis_shelter_many_to_many_relationship():
    engine = create_engine("sqlite:///:memory:")
    for table in (Crisis.__table__, Shelter.__table__, CrisesShelters.__table__):
        table.create(engine)

    crisis_id = uuid.uuid4()
    shelter_id = uuid.uuid4()

    with Session(engine) as session:
        crisis = Crisis(
            id=crisis_id,
            name="Enchente Teste",
            type=CrisisType.FLOOD,
            status=CrisisStatus.ACTIVE,
            state=BrazilianState.SP,
            city="Sao Paulo",
            severity_initial=3,
            created_by=uuid.uuid4(),
        )
        shelter = Shelter(
            id=shelter_id,
            responsible_user_id=uuid.uuid4(),
            created_by=uuid.uuid4(),
            name="Abrigo Central",
            address="Rua Principal, 100",
            capacity=100,
            occupation=25,
            shelter_type=ShelterType.INSTITUTIONAL,
            status=ShelterStatus.ACTIVE,
            verified=True,
        )
        crisis.shelters.append(shelter)

        session.add(crisis)
        session.commit()
        session.expire_all()

        saved_crisis = session.get(Crisis, crisis_id)
        saved_shelter = session.get(Shelter, shelter_id)

        assert saved_crisis is not None
        assert saved_shelter is not None
        assert saved_crisis.shelters == [saved_shelter]
        assert saved_shelter.crises == [saved_crisis]

        session.delete(saved_crisis)
        session.commit()
        session.expire_all()

        assert session.get(Crisis, crisis_id) is None
        assert session.get(Shelter, shelter_id) is not None
