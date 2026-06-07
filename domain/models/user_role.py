import uuid
from datetime import datetime

from sqlalchemy import Enum as PgEnum, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain.auth.enums import Role
from utils.database import Base

user_role_pg = PgEnum(
    Role,
    name="user_role",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class UserRole(Base):
    """Junction table — a user can hold any combination of roles."""

    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role: Mapped[Role] = mapped_column(user_role_pg, primary_key=True)
    granted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
