from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from domain.auth.enums import Role
from domain.schemas.enums import OrganizationType

PUBLIC_REGISTRATION_ROLES = {Role.CRISIS_MANAGER, Role.SHELTER_MANAGER}


class _RegistrationRequestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    roles: list[Role] = Field(min_length=1)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("roles")
    @classmethod
    def _validate_public_roles(cls, value: list[Role]) -> list[Role]:
        seen: set[Role] = set()
        unique: list[Role] = []
        for role in value:
            if role in seen:
                continue
            seen.add(role)
            unique.append(role)

        forbidden = [role for role in unique if role not in PUBLIC_REGISTRATION_ROLES]
        if forbidden:
            label = ", ".join(role.value for role in forbidden)
            raise ValueError(f"roles not allowed for public registration: {label}")
        return unique


class ExistingOrganizationRegistrationRequest(_RegistrationRequestBase):
    organization_id: UUID


class NewOrganizationRegistrationRequest(_RegistrationRequestBase):
    organization_name: str = Field(min_length=1, max_length=200)
    organization_cnpj: str | None = Field(default=None, max_length=32)
    organization_type: OrganizationType = OrganizationType.SHELTER_OPERATOR
    organization_contact_email: EmailStr | None = None


class RegistrationRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    request_type: str
    name: str
    email: EmailStr
    roles: list[Role]
    phone: str | None = None
    organization_id: UUID | None = None
    new_organization_name: str | None = None
    new_organization_cnpj: str | None = None
    new_organization_type: OrganizationType | None = None
    new_organization_contact_email: EmailStr | None = None
    user_id: UUID | None = None
    created_organization_id: UUID | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime


class OrganizationSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
