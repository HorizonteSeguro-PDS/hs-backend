"""Schemas pra check-in / check-out de pessoas num abrigo.

POST /shelters/{id}/check-ins  → CheckInRequest, CheckInResponse
POST /shelters/{id}/check-outs → CheckOutRequest, CheckOutResponse
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.schemas.enums import VulnerabilityType


# --------------------------------------------------------------------------- #
# Sub-schemas comuns                                                          #
# --------------------------------------------------------------------------- #


class BeneficiaryRead(BaseModel):
    """Forma reduzida do beneficiario pra embutir em responses de stay."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    cpf: str | None = None
    birth_date: date | None = None
    age: int | None = None
    phone: str | None = None
    vulnerability: VulnerabilityType | None = None


class ShelterStayRead(BaseModel):
    """Forma reduzida do stay pra embutir em responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    beneficiary_id: UUID
    shelter_id: UUID
    checked_in_at: datetime
    checked_out_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Check-in                                                                    #
# --------------------------------------------------------------------------- #


class CheckInRequest(BaseModel):
    """Payload pra POST /shelters/{shelter_id}/check-ins.

    CPF é obrigatorio — é a chave que identifica o beneficiario entre check-ins
    (se ja existe alguem com esse CPF, reusa; senao cria novo). Use CPF
    formatado (NNN.NNN.NNN-NN) ou so digitos — o backend nao normaliza.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    cpf: str = Field(min_length=11, max_length=14)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=32)
    vulnerability: VulnerabilityType | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CheckInResponse(BaseModel):
    """Resposta do check-in — beneficiario + stay aberto + occupancy atualizada."""

    beneficiary: BeneficiaryRead
    stay: ShelterStayRead
    shelter_occupation: int = Field(
        ge=0, description="Occupation do shelter DEPOIS do check-in."
    )


# --------------------------------------------------------------------------- #
# Check-out                                                                   #
# --------------------------------------------------------------------------- #


class CheckOutRequest(BaseModel):
    """Identifica quem ta saindo. CPF é o caminho principal porque o front
    busca por CPF; beneficiary_id fica como fallback se o front tiver o id.
    """

    model_config = ConfigDict(extra="forbid")

    cpf: str | None = Field(default=None, min_length=11, max_length=14)
    beneficiary_id: UUID | None = None


class CheckOutResponse(BaseModel):
    """Resposta do check-out — stay fechado + occupancy atualizada."""

    beneficiary: BeneficiaryRead
    stay: ShelterStayRead
    shelter_occupation: int = Field(
        ge=0, description="Occupation do shelter DEPOIS do check-out."
    )
