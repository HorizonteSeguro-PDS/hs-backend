from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from domain.auth.enums import Role


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Plaintext password. Hashed server-side with bcrypt before storage.",
    )
    roles: list[Role] = Field(
        min_length=1,
        description="One or more roles to assign at registration time.",
    )
    organization_id: UUID | None = None
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("roles")
    @classmethod
    def _no_duplicates(cls, value: list[Role]) -> list[Role]:
        seen: set[Role] = set()
        unique: list[Role] = []
        for r in value:
            if r in seen:
                continue
            seen.add(r)
            unique.append(r)
        return unique


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    roles: list[Role]
    organization_id: UUID | None = None
    phone: str | None = None
    verified: bool
    created_at: datetime
    last_login_at: datetime | None = None
