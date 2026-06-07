import uuid
from typing import Any

from sqlalchemy import VARCHAR, Enum as PgEnum, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain.schemas.enums import RoleScope
from utils.database import Base

role_scope_pg = PgEnum(
    RoleScope,
    name="role_scope",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    scope: Mapped[RoleScope] = mapped_column(role_scope_pg, nullable=False)
    permissions: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
