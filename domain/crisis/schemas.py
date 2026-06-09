from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.schemas.enums import BrazilianState, SeverityLabel


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


# Aliases aceitos no POST /crises (em PT/EN, com ou sem acento). Mapeia pro
# inteiro 0-3 que persiste no banco.
_SEVERITY_ALIASES: dict[str, int] = {
    "inativo": 0,
    "inativa": 0,
    "baixa": 1,
    "low": 1,
    "media": 2,
    "média": 2,
    "medium": 2,
    "alta": 3,
    "high": 3,
}


class CrisisBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    type: CrisisType
    description: str | None = None
    state: str = Field(
        min_length=2, max_length=2, description="UF brasileira (2 letras)"
    )
    city: str = Field(min_length=1, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    start_date: date | None = None
    status: CrisisStatus = CrisisStatus.ACTIVE
    severity_initial: int | None = Field(default=None, ge=0, le=3)

    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
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
        if len(normalized) == 2 and normalized.isalpha():
            return normalized.upper()
        return _STATE_NAMES.get(normalized, value)


class CrisisCreate(CrisisBase):
    severity: str | int | None = None

    @model_validator(mode="after")
    def _map_modal_severity(self) -> "CrisisCreate":
        # Se o front mandou severity_initial direto, respeita.
        if self.severity_initial is not None or self.severity is None:
            return self
        if isinstance(self.severity, int):
            if not 0 <= self.severity <= 3:
                raise ValueError("severity must be between 0 and 3")
            self.severity_initial = self.severity
            return self
        value = _SEVERITY_ALIASES.get(self.severity.strip().lower())
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
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    severity_initial: int | None = Field(default=None, ge=0, le=3)
    severity_calculated: int | None = Field(default=None, ge=0, le=3)


class CrisisClose(BaseModel):
    close_reason: str = Field(min_length=1)


class CrisisRead(BaseModel):
    """Internal write shape — write endpoints (POST/PATCH/close/reopen) ainda
    devolvem isso, pra preservar visibilidade dos campos brutos (severity_initial
    em int, status enum completo, etc.). O front consumidor da listagem usa as
    *Response classes abaixo.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None = None
    name: str
    type: CrisisType
    description: str | None = None
    status: CrisisStatus
    state: str
    city: str
    latitude: float | None = None
    longitude: float | None = None
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
    """Forma exata que o front espera em GET /crises (array plano).

    Severity vai como string label (regra de negocio no back); status é
    projetado em `active: bool` porque o front so distingue ativo/inativo.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    severity: SeverityLabel
    state: str
    city: str
    latitude: float | None = None
    longitude: float | None = None
    start_date: date | None = None
    shelters_count: int = Field(ge=0)
    active: bool


class ShelterInCrisisResponse(BaseModel):
    """Forma de cada shelter dentro de GET /crises/{id}.

    `urgent_needs` vai vazio enquanto o modelo de shelter_needs nao existe —
    é placeholder pro contrato do front nao quebrar.

    `current_occupancy` é o `occupation` do model renomeado pro contrato do
    front. `severity` é derivado de occupation/capacity (regra de negocio
    no back).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    city: str
    state: BrazilianState
    latitude: float | None = None
    longitude: float | None = None
    urgent_needs: list[str] = Field(default_factory=list)
    capacity: int
    current_occupancy: int
    severity: SeverityLabel


class CrisisDetailResponse(CrisisListItemResponse):
    shelters: list[ShelterInCrisisResponse] = Field(default_factory=list)
