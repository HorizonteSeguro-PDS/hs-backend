import uuid
from datetime import datetime

from sqlalchemy import VARCHAR, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base


class RegistrationRequest(Base):
    __tablename__ = "registration_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    status: Mapped[str] = mapped_column(
        VARCHAR, nullable=False, server_default="pending"
    )
    request_type: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    email: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    phone: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    password_hash: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", name="fk_registration_requests_organization_id"),
        nullable=True,
    )
    new_organization_name: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    new_organization_cnpj: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    new_organization_type: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    new_organization_contact_email: Mapped[str | None] = mapped_column(
        VARCHAR, nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_registration_requests_user_id_users"),
        nullable=True,
    )
    created_organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_registration_requests_created_organization_id",
        ),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_registration_requests_reviewed_by_users"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_registration_requests_status", "status"),
        Index("ix_registration_requests_email_status", "email", "status"),
    )
