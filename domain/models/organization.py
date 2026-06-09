import uuid
from datetime import datetime

from sqlalchemy import VARCHAR, Enum as PgEnum, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain.schemas.enums import OrganizationType
from utils.database import Base

organization_type_pg = PgEnum(
    OrganizationType,
    name="organization_type",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    cnpj: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    type: Mapped[OrganizationType] = mapped_column(organization_type_pg, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("cnpj", name="uq_organizations_cnpj"),)
