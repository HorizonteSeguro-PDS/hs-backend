from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from domain.schemas.enums import BrazilianState, ShelterStatus, ShelterType


class ShelterBase(BaseModel):
    organization_id: UUID | None = None
    responsible_user_id: UUID
    verified_by: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    address: str = Field(min_length=1, max_length=255)
    neighborhood: str | None = Field(default=None, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    state: BrazilianState
    cep: str | None = Field(default=None, max_length=9)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int = Field(ge=0)
    entry_requirements: str | None = Field(default=None, max_length=1000)
    attended_special_needs: str | None = Field(default=None, max_length=1000)
    occupation: int = Field(default=0, ge=0)
    shelter_type: ShelterType
    status: ShelterStatus = ShelterStatus.PREPARING
    bio: str | None = Field(default=None, max_length=2000)
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
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    address: str = Field(min_length=1, max_length=255)
    neighborhood: str | None = Field(default=None, max_length=120)
    city: str = Field(min_length=1, max_length=120)
    state: BrazilianState
    cep: str | None = Field(default=None, max_length=9)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int = Field(ge=0)
    entry_requirements: str | None = Field(default=None, max_length=1000)
    attended_special_needs: str | None = Field(default=None, max_length=1000)
    occupation: int = Field(default=0, ge=0)
    shelter_type: ShelterType
    bio: str | None = Field(default=None, max_length=2000)

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
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    neighborhood: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    state: BrazilianState | None = None
    cep: str | None = Field(default=None, max_length=9)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int | None = Field(default=None, ge=0)
    entry_requirements: str | None = Field(default=None, max_length=1000)
    attended_special_needs: str | None = Field(default=None, max_length=1000)
    occupation: int | None = Field(default=None, ge=0)
    shelter_type: ShelterType | None = None
    status: ShelterStatus | None = None
    bio: str | None = Field(default=None, max_length=2000)
    verified: bool | None = None


class ShelterUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    neighborhood: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    state: BrazilianState | None = None
    cep: str | None = Field(default=None, max_length=9)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int | None = Field(default=None, ge=0)
    entry_requirements: str | None = Field(default=None, max_length=1000)
    attended_special_needs: str | None = Field(default=None, max_length=1000)
    occupation: int | None = Field(default=None, ge=0)
    shelter_type: ShelterType | None = None
    bio: str | None = Field(default=None, max_length=2000)


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
    neighborhood: str | None = None
    city: str
    state: BrazilianState
    cep: str | None = None
    capacity: int
    occupation: int
    entry_requirements: str | None = None
    attended_special_needs: str | None = None
    shelter_type: ShelterType
    status: ShelterStatus
    verified: bool


class ShelterSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    address: str
    city: str
    state: BrazilianState
    capacity: int
    occupation: int
    status: ShelterStatus
