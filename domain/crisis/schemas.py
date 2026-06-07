from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.shelter.schemas import ShelterSummaryResponse


class CrisisBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: CrisisType
    description: str | None = None
    state: str = Field(
        min_length=2, max_length=2, description="UF brasileira (2 letras)"
    )
    city: str = Field(min_length=1, max_length=120)
    severity_initial: int | None = Field(default=None, ge=1, le=5)


class CrisisCreate(CrisisBase):
    pass


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
    name: str
    type: CrisisType
    description: str | None = None
    status: CrisisStatus
    state: str
    city: str
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
    name: str
    type: CrisisType
    status: CrisisStatus
    state: str
    city: str
    severity_initial: int | None = None
    severity_calculated: int | None = None
    created_at: datetime
    shelters_count: int = Field(ge=0)


class CrisisDetailResponse(CrisisRead):
    shelters: list[ShelterSummaryResponse] = Field(default_factory=list)
