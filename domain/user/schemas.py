from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from domain.auth.enums import Role


class UserRegister(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Plaintext password. Hashed server-side with bcrypt before storage.",
    )
    role: Role = Field(
        description="One of: master, standard, oversight.",
    )
    organization_id: UUID | None = None
    phone: str | None = Field(default=None, max_length=32)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: EmailStr
    role: Role
    organization_id: UUID | None = None
    phone: str | None = None
    verified: bool
    created_at: datetime
    last_login_at: datetime | None = None
