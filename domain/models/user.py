import uuid
from datetime import datetime

from sqlalchemy import VARCHAR, Boolean, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    # FK to organizations(id) — constraint lives in the migration
    # (fk_users_organization_id_organizations); not declared here because the
    # Organization model is not registered in metadata.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    email: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    phone: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    password_hash: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)
