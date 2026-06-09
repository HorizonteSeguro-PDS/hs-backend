"""Tests for ShelterStayService — check-in / check-out atomicos.

Usa SQLite in-memory pra exercitar a logica de stays + occupation.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from domain.errors.http import ResourceNotFoundError
from domain.models.beneficiary import Beneficiary
from domain.models.shelter import Shelter
from domain.models.shelter_stay import ShelterStay
from domain.schemas.enums import (
    BrazilianState,
    ShelterStatus,
    ShelterType,
    VulnerabilityType,
)
from domain.shelter_stay.schemas import CheckInRequest, CheckOutRequest
from services.shelter_stay_service import (
    BeneficiaryAlreadyShelteredError,
    CheckOutTargetMissingError,
    ShelterFullError,
    ShelterStayService,
    _compute_age,
)


def _setup_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    for table in (
        Shelter.__table__,
        Beneficiary.__table__,
        ShelterStay.__table__,
    ):
        table.create(engine)
    return Session(engine)


def _seed_shelter(
    session: Session,
    *,
    capacity: int = 10,
    occupation: int = 0,
) -> Shelter:
    shelter = Shelter(
        id=uuid.uuid4(),
        organization_id=None,
        responsible_user_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        name="Abrigo Teste",
        address="Rua A, 1",
        city="Maceio",
        state=BrazilianState.AL,
        capacity=capacity,
        occupation=occupation,
        shelter_type=ShelterType.INSTITUTIONAL,
        status=ShelterStatus.ACTIVE,
        verified=True,
    )
    session.add(shelter)
    session.commit()
    return shelter


def _payload(
    *,
    cpf: str = "123.456.789-00",
    name: str = "João Teste",
    birth_date: date | None = None,
    phone: str | None = None,
    vulnerability: VulnerabilityType | None = None,
) -> CheckInRequest:
    return CheckInRequest(
        cpf=cpf,
        name=name,
        birth_date=birth_date,
        phone=phone,
        vulnerability=vulnerability,
    )


# --------------------------------------------------------------------------- #
# _compute_age                                                                #
# --------------------------------------------------------------------------- #


def test_compute_age_returns_none_for_none_birth_date():
    assert _compute_age(None) is None


def test_compute_age_handles_future_birth_date():
    future = datetime.now(timezone.utc).date() + timedelta(days=10)
    assert _compute_age(future) is None


def test_compute_age_subtracts_a_year_if_birthday_not_yet_reached():
    today = datetime.now(timezone.utc).date()
    # Aniversario em 30 dias -> ainda nao chegou neste ano
    upcoming = (today + timedelta(days=30)).replace(year=today.year - 10)
    assert _compute_age(upcoming) == 9


def test_compute_age_counts_full_year_after_birthday():
    today = datetime.now(timezone.utc).date()
    # Aniversario foi 30 dias atras
    past = (today - timedelta(days=30)).replace(year=today.year - 10)
    assert _compute_age(past) == 10


# --------------------------------------------------------------------------- #
# check_in                                                                    #
# --------------------------------------------------------------------------- #


class TestCheckIn:
    def test_creates_beneficiary_and_opens_stay(self):
        with _setup_session() as session:
            shelter = _seed_shelter(session, capacity=10, occupation=2)
            service = ShelterStayService(session)

            response = service.check_in(shelter_id=shelter.id, payload=_payload())
            session.commit()

            assert response.shelter_occupation == 3
            assert response.beneficiary.cpf == "123.456.789-00"
            assert response.beneficiary.name == "João Teste"
            assert response.stay.shelter_id == shelter.id
            assert response.stay.checked_out_at is None

            # Estado persistido
            shelter_refreshed = session.get(Shelter, shelter.id)
            assert shelter_refreshed.occupation == 3
            assert (
                session.scalar(
                    select(ShelterStay).where(ShelterStay.shelter_id == shelter.id)
                )
                is not None
            )

    def test_computes_age_from_birth_date(self):
        with _setup_session() as session:
            shelter = _seed_shelter(session)
            service = ShelterStayService(session)

            today = datetime.now(timezone.utc).date()
            bday = (today - timedelta(days=365 * 30 + 5)).replace(
                month=today.month, day=today.day
            )

            response = service.check_in(
                shelter_id=shelter.id,
                payload=_payload(birth_date=bday),
            )
            session.commit()

            assert response.beneficiary.birth_date == bday
            assert response.beneficiary.age is not None
            assert response.beneficiary.age >= 29

    def test_reuses_beneficiary_by_cpf_and_updates_fields(self):
        with _setup_session() as session:
            shelter = _seed_shelter(session, capacity=10)
            service = ShelterStayService(session)

            service.check_in(
                shelter_id=shelter.id,
                payload=_payload(name="Old Name", phone=None),
            )
            session.commit()
            service.check_out(
                shelter_id=shelter.id,
                payload=CheckOutRequest(cpf="123.456.789-00"),
            )
            session.commit()

            # Mesmo CPF, novo nome e telefone — deve atualizar
            response = service.check_in(
                shelter_id=shelter.id,
                payload=_payload(name="New Name", phone="+5582999999999"),
            )
            session.commit()

            assert response.beneficiary.name == "New Name"
            assert response.beneficiary.phone == "+5582999999999"
            # Mesma row?
            rows = session.scalars(
                select(Beneficiary).where(Beneficiary.cpf == "123.456.789-00")
            ).all()
            assert len(rows) == 1

    def test_blocks_when_shelter_is_full(self):
        with _setup_session() as session:
            shelter = _seed_shelter(session, capacity=2, occupation=2)
            service = ShelterStayService(session)

            with pytest.raises(ShelterFullError) as exc:
                service.check_in(shelter_id=shelter.id, payload=_payload())

            assert exc.value.status_code == 409
            assert exc.value.detail["error"] == "shelter_full"
            # Estado nao mudou
            assert session.get(Shelter, shelter.id).occupation == 2

    def test_blocks_when_beneficiary_already_sheltered_elsewhere(self):
        with _setup_session() as session:
            shelter_a = _seed_shelter(session, capacity=10, occupation=0)
            shelter_b = _seed_shelter(session, capacity=10, occupation=0)
            service = ShelterStayService(session)

            service.check_in(shelter_id=shelter_a.id, payload=_payload())
            session.commit()

            with pytest.raises(BeneficiaryAlreadyShelteredError) as exc:
                service.check_in(shelter_id=shelter_b.id, payload=_payload())

            assert exc.value.status_code == 409
            assert exc.value.detail["error"] == "beneficiary_already_sheltered"
            assert exc.value.detail["current_shelter_id"] == str(shelter_a.id)
            # shelter_b nao foi tocado
            assert session.get(Shelter, shelter_b.id).occupation == 0

    def test_raises_404_when_shelter_missing(self):
        with _setup_session() as session:
            service = ShelterStayService(session)
            with pytest.raises(ResourceNotFoundError):
                service.check_in(shelter_id=uuid.uuid4(), payload=_payload())


# --------------------------------------------------------------------------- #
# check_out                                                                   #
# --------------------------------------------------------------------------- #


class TestCheckOut:
    def test_closes_stay_and_decrements_occupation(self):
        with _setup_session() as session:
            shelter = _seed_shelter(session, capacity=10, occupation=0)
            service = ShelterStayService(session)

            service.check_in(shelter_id=shelter.id, payload=_payload())
            session.commit()
            assert session.get(Shelter, shelter.id).occupation == 1

            response = service.check_out(
                shelter_id=shelter.id,
                payload=CheckOutRequest(cpf="123.456.789-00"),
            )
            session.commit()

            assert response.shelter_occupation == 0
            assert response.stay.checked_out_at is not None
            assert session.get(Shelter, shelter.id).occupation == 0

    def test_accepts_beneficiary_id_as_target(self):
        with _setup_session() as session:
            shelter = _seed_shelter(session)
            service = ShelterStayService(session)

            checkin = service.check_in(shelter_id=shelter.id, payload=_payload())
            session.commit()

            response = service.check_out(
                shelter_id=shelter.id,
                payload=CheckOutRequest(beneficiary_id=checkin.beneficiary.id),
            )
            session.commit()

            assert response.shelter_occupation == 0

    def test_blocks_when_payload_has_neither_cpf_nor_id(self):
        with _setup_session() as session:
            shelter = _seed_shelter(session)
            service = ShelterStayService(session)

            with pytest.raises(CheckOutTargetMissingError) as exc:
                service.check_out(shelter_id=shelter.id, payload=CheckOutRequest())

            assert exc.value.status_code == 422

    def test_404_when_no_open_stay_at_this_shelter(self):
        with _setup_session() as session:
            shelter_a = _seed_shelter(session)
            shelter_b = _seed_shelter(session)
            service = ShelterStayService(session)

            service.check_in(shelter_id=shelter_a.id, payload=_payload())
            session.commit()

            # Tentar check-out em B, mas pessoa esta em A
            with pytest.raises(ResourceNotFoundError):
                service.check_out(
                    shelter_id=shelter_b.id,
                    payload=CheckOutRequest(cpf="123.456.789-00"),
                )

    def test_404_when_beneficiary_does_not_exist(self):
        with _setup_session() as session:
            shelter = _seed_shelter(session)
            service = ShelterStayService(session)

            with pytest.raises(ResourceNotFoundError):
                service.check_out(
                    shelter_id=shelter.id,
                    payload=CheckOutRequest(cpf="999.999.999-99"),
                )

    def test_occupation_does_not_go_negative_if_already_zero(self):
        """Defensivo: se um stay foi criado manualmente e o occupation nao foi
        atualizado, check-out nao decrementa abaixo de 0.
        """
        with _setup_session() as session:
            shelter = _seed_shelter(session, capacity=10, occupation=0)
            beneficiary = Beneficiary(
                id=uuid.uuid4(),
                cpf="123.456.789-00",
                name="Test",
            )
            session.add(beneficiary)
            session.add(
                ShelterStay(
                    id=uuid.uuid4(),
                    beneficiary_id=beneficiary.id,
                    shelter_id=shelter.id,
                    checked_in_at=datetime.now(timezone.utc),
                    checked_out_at=None,
                )
            )
            session.commit()

            service = ShelterStayService(session)
            response = service.check_out(
                shelter_id=shelter.id,
                payload=CheckOutRequest(cpf="123.456.789-00"),
            )
            session.commit()

            assert response.shelter_occupation == 0
