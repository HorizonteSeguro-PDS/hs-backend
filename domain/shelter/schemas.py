from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.schemas.enums import ShelterStatus, ShelterType


class ShelterBase(BaseModel):
    organization_id: UUID | None = None
    responsible_user_id: UUID
    verified_by: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int = Field(ge=0)
    occupation: int = Field(default=0, ge=0)
    shelter_type: ShelterType
    status: ShelterStatus = ShelterStatus.PREPARING
    verified: bool = False


class ShelterCreate(ShelterBase):
    @model_validator(mode="after")
    def _occupation_must_fit_capacity(self) -> "ShelterCreate":
        if self.occupation > self.capacity:
            raise ValueError("occupation must be less than or equal to capacity")
        return self


class ShelterCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int = Field(ge=0)
    occupation: int = Field(default=0, ge=0)
    shelter_type: ShelterType

    @model_validator(mode="after")
    def _occupation_must_fit_capacity(self) -> "ShelterCreateRequest":
        if self.occupation > self.capacity:
            raise ValueError("occupation must be less than or equal to capacity")
        return self


class ShelterUpdate(BaseModel):
    organization_id: UUID | None = None
    responsible_user_id: UUID | None = None
    created_by: UUID | None = None
    verified_by: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int | None = Field(default=None, ge=0)
    occupation: int | None = Field(default=None, ge=0)
    shelter_type: ShelterType | None = None
    status: ShelterStatus | None = None
    verified: bool | None = None


class ShelterUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int | None = Field(default=None, ge=0)
    occupation: int | None = Field(default=None, ge=0)
    shelter_type: ShelterType | None = None


class ShelterRead(ShelterBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class ShelterListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str
    capacity: int
    occupation: int
    shelter_type: ShelterType
    status: ShelterStatus
    verified: bool


class ShelterSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str
    capacity: int
    occupation: int
    status: ShelterStatus
