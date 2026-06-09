"""Service de check-in / check-out de pessoas em abrigos.

Duas operações atômicas:
  - check_in(shelter_id, payload, actor_id)
  - check_out(shelter_id, payload, actor_id)

Cada uma faz tudo dentro da mesma transaction (caller commita).

Regras de negócio:
  - CPF é a chave do beneficiário entre check-ins. Se ja existir, reusa.
  - Não pode haver mais de um stay aberto por beneficiário (independente
    do abrigo). Se vier alguém ja acolhido em outro abrigo, 409.
  - Não pode fazer check-in num abrigo cheio (occupation >= capacity), 409.
  - Check-out exige stay aberto naquele abrigo, 404 caso contrario.
  - `Shelter.occupation` é incrementado/decrementado atomicamente.
"""

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.errors.http import ResourceNotFoundError
from domain.models.beneficiary import Beneficiary
from domain.models.shelter import Shelter
from domain.models.shelter_stay import ShelterStay
from domain.shelter_stay.schemas import (
    BeneficiaryRead,
    CheckInRequest,
    CheckInResponse,
    CheckOutRequest,
    CheckOutResponse,
    ShelterStayRead,
)


class ShelterFullError(HTTPException):
    """409 — tentou check-in num abrigo com occupation >= capacity."""

    def __init__(self, *, capacity: int) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "shelter_full",
                "capacity": capacity,
            },
        )


class BeneficiaryAlreadyShelteredError(HTTPException):
    """409 — beneficiário já tem stay aberto em algum abrigo (talvez outro).

    O front deve fazer check-out no abrigo anterior antes de tentar de novo.
    """

    def __init__(self, *, current_shelter_id: UUID) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "beneficiary_already_sheltered",
                "current_shelter_id": str(current_shelter_id),
            },
        )


class CheckOutTargetMissingError(HTTPException):
    """422 — payload de check-out veio sem cpf nem beneficiary_id."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "check_out_target_missing",
                "message": "Either cpf or beneficiary_id is required.",
            },
        )


def _compute_age(birth_date: date | None) -> int | None:
    """Idade hoje. Retorna None se birth_date for None ou estiver no futuro."""
    if birth_date is None:
        return None
    today = datetime.now(timezone.utc).date()
    if birth_date > today:
        return None
    years = today.year - birth_date.year
    # Ajusta se ainda nao fez aniversario este ano.
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


class ShelterStayService:
    """Coordena beneficiarios + stays + cache de occupation."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------ #
    # check_in                                                            #
    # ------------------------------------------------------------------ #

    def check_in(
        self,
        *,
        shelter_id: UUID,
        payload: CheckInRequest,
    ) -> CheckInResponse:
        shelter = self._require_shelter(shelter_id)

        # Validacao de lotacao antes de tocar em qualquer coisa.
        if shelter.occupation >= shelter.capacity:
            raise ShelterFullError(capacity=shelter.capacity)

        # Get-or-create beneficiario por CPF.
        beneficiary = self._get_or_create_beneficiary(payload)

        # Garante que beneficiario nao esta acolhido em lugar nenhum agora.
        open_stay = self._find_any_open_stay(beneficiary.id)
        if open_stay is not None:
            raise BeneficiaryAlreadyShelteredError(
                current_shelter_id=open_stay.shelter_id
            )

        # Abre o stay.
        stay = ShelterStay(
            beneficiary_id=beneficiary.id,
            shelter_id=shelter.id,
            checked_in_at=datetime.now(timezone.utc),
            checked_out_at=None,
        )
        self.session.add(stay)

        # Incrementa occupation atomicamente (no MESMO flush).
        shelter.occupation = shelter.occupation + 1

        self.session.flush()
        self.session.refresh(stay)
        self.session.refresh(shelter)

        return CheckInResponse(
            beneficiary=BeneficiaryRead.model_validate(beneficiary),
            stay=ShelterStayRead.model_validate(stay),
            shelter_occupation=shelter.occupation,
        )

    # ------------------------------------------------------------------ #
    # check_out                                                           #
    # ------------------------------------------------------------------ #

    def check_out(
        self,
        *,
        shelter_id: UUID,
        payload: CheckOutRequest,
    ) -> CheckOutResponse:
        if payload.cpf is None and payload.beneficiary_id is None:
            raise CheckOutTargetMissingError()

        shelter = self._require_shelter(shelter_id)

        beneficiary = self._find_beneficiary(payload)
        if beneficiary is None:
            raise ResourceNotFoundError("beneficiary not found")

        # Stay aberto NESTE shelter especificamente.
        open_stay = self.session.scalar(
            select(ShelterStay).where(
                ShelterStay.beneficiary_id == beneficiary.id,
                ShelterStay.shelter_id == shelter.id,
                ShelterStay.checked_out_at.is_(None),
            )
        )
        if open_stay is None:
            raise ResourceNotFoundError(
                "no open stay for this beneficiary at this shelter"
            )

        # Fecha o stay e decrementa occupation (clamp em 0 pra evitar negativo
        # se o seed/admin mexeu manualmente).
        open_stay.checked_out_at = datetime.now(timezone.utc)
        shelter.occupation = max(shelter.occupation - 1, 0)

        self.session.flush()
        self.session.refresh(open_stay)
        self.session.refresh(shelter)

        return CheckOutResponse(
            beneficiary=BeneficiaryRead.model_validate(beneficiary),
            stay=ShelterStayRead.model_validate(open_stay),
            shelter_occupation=shelter.occupation,
        )

    # ------------------------------------------------------------------ #
    # Helpers privados                                                    #
    # ------------------------------------------------------------------ #

    def _require_shelter(self, shelter_id: UUID) -> Shelter:
        shelter = self.session.get(Shelter, shelter_id)
        if shelter is None:
            raise ResourceNotFoundError("shelter not found")
        return shelter

    def _get_or_create_beneficiary(self, payload: CheckInRequest) -> Beneficiary:
        existing = self.session.scalar(
            select(Beneficiary).where(Beneficiary.cpf == payload.cpf)
        )
        if existing is not None:
            # Reconcilia campos opcionais — gestor pode ter atualizado info.
            self._update_beneficiary_fields(existing, payload)
            self.session.flush()
            return existing

        beneficiary = Beneficiary(
            cpf=payload.cpf,
            name=payload.name,
            birth_date=payload.birth_date,
            age=_compute_age(payload.birth_date),
            phone=payload.phone,
            vulnerability=payload.vulnerability,
            notes=payload.notes,
        )
        self.session.add(beneficiary)
        self.session.flush()
        return beneficiary

    @staticmethod
    def _update_beneficiary_fields(
        beneficiary: Beneficiary, payload: CheckInRequest
    ) -> None:
        """Atualiza campos no beneficiario existente — só sobrescreve com valor
        não-vazio pra evitar zerar dados acidentalmente.
        """
        beneficiary.name = payload.name  # nome é sempre atualizado (required)
        if payload.birth_date is not None:
            beneficiary.birth_date = payload.birth_date
            beneficiary.age = _compute_age(payload.birth_date)
        if payload.phone is not None:
            beneficiary.phone = payload.phone
        if payload.vulnerability is not None:
            beneficiary.vulnerability = payload.vulnerability
        if payload.notes is not None:
            beneficiary.notes = payload.notes

    def _find_any_open_stay(self, beneficiary_id: UUID) -> ShelterStay | None:
        return self.session.scalar(
            select(ShelterStay).where(
                ShelterStay.beneficiary_id == beneficiary_id,
                ShelterStay.checked_out_at.is_(None),
            )
        )

    def _find_beneficiary(self, payload: CheckOutRequest) -> Beneficiary | None:
        if payload.beneficiary_id is not None:
            return self.session.get(Beneficiary, payload.beneficiary_id)
        return self.session.scalar(
            select(Beneficiary).where(Beneficiary.cpf == payload.cpf)
        )


__all__ = [
    "ShelterStayService",
    "ShelterFullError",
    "BeneficiaryAlreadyShelteredError",
    "CheckOutTargetMissingError",
]
