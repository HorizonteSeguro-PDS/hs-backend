from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.shelter.schemas import ShelterSummaryResponse


_STATE_NAMES = {
    "acre": "AC",
    "alagoas": "AL",
    "amapa": "AP",
    "amazonas": "AM",
    "bahia": "BA",
    "ceara": "CE",
    "distrito federal": "DF",
    "espirito santo": "ES",
    "goias": "GO",
    "maranhao": "MA",
    "mato grosso": "MT",
    "mato grosso do sul": "MS",
    "minas gerais": "MG",
    "para": "PA",
    "paraiba": "PB",
    "parana": "PR",
    "pernambuco": "PE",
    "piaui": "PI",
    "rio de janeiro": "RJ",
    "rio grande do norte": "RN",
    "rio grande do sul": "RS",
    "rondonia": "RO",
    "roraima": "RR",
    "santa catarina": "SC",
    "sao paulo": "SP",
    "sergipe": "SE",
    "tocantins": "TO",
}


class CrisisBase(BaseModel):
    organization_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    type: CrisisType
    description: str | None = None
    state: str = Field(
        min_length=2, max_length=2, description="UF brasileira (2 letras)"
    )
    city: str = Field(min_length=1, max_length=120)
    start_date: date | None = None
    status: CrisisStatus = CrisisStatus.ACTIVE
    severity_initial: int | None = Field(default=None, ge=1, le=5)

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower()
        return value

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        aliases = {
            "ativa": CrisisStatus.ACTIVE.value,
            "active": CrisisStatus.ACTIVE.value,
            "fechada": CrisisStatus.CLOSED.value,
            "closed": CrisisStatus.CLOSED.value,
        }
        return aliases.get(normalized, normalized)

    @field_validator("state", mode="before")
    @classmethod
    def _normalize_state(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = (
            value.strip()
            .lower()
            .replace("á", "a")
            .replace("ã", "a")
            .replace("â", "a")
            .replace("é", "e")
            .replace("ê", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ô", "o")
            .replace("õ", "o")
            .replace("ú", "u")
            .replace("ç", "c")
        )
        return _STATE_NAMES.get(normalized, value)


class CrisisCreate(CrisisBase):
    severity: str | int | None = None

    @model_validator(mode="after")
    def _map_modal_severity(self) -> "CrisisCreate":
        if self.severity_initial is not None or self.severity is None:
            return self
        if isinstance(self.severity, int):
            if not 1 <= self.severity <= 5:
                raise ValueError("severity must be between 1 and 5")
            self.severity_initial = self.severity
            return self
        severity_aliases = {
            "baixa": 2,
            "media": 3,
            "média": 3,
            "alta": 4,
            "critica": 5,
            "crítica": 5,
        }
        value = severity_aliases.get(self.severity.strip().lower())
        if value is None:
            raise ValueError("invalid severity")
        self.severity_initial = value
        return self


class CrisisUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    type: CrisisType | None = None
    description: str | None = None
    state: str | None = Field(default=None, min_length=2, max_length=2)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    severity_initial: int | None = Field(default=None, ge=1, le=5)
    severity_calculated: int | None = Field(default=None, ge=1, le=5)


class CrisisClose(BaseModel):
    close_reason: str = Field(min_length=1)


class CrisisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None = None
    name: str
    type: CrisisType
    description: str | None = None
    status: CrisisStatus
    state: str
    city: str
    start_date: date | None = None
    severity_initial: int | None = None
    severity_calculated: int | None = None
    severity_calculated_at: datetime | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    closed_by: UUID | None = None
    close_reason: str | None = None


class CrisisListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None = None
    name: str
    type: CrisisType
    status: CrisisStatus
    state: str
    city: str
    start_date: date | None = None
    severity_initial: int | None = None
    severity_calculated: int | None = None
    created_at: datetime
    shelters_count: int = Field(ge=0)


class CrisisDetailResponse(CrisisRead):
    shelters: list[ShelterSummaryResponse] = Field(default_factory=list)
