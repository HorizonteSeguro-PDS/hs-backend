import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import VARCHAR, Boolean, Enum as PgEnum, Float, Index, Integer, func, String
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.models.crises_shelters import CrisesShelters
from domain.schemas.enums import BrazilianState, ShelterStatus, ShelterType
from utils.database import Base

if TYPE_CHECKING:
    from domain.models.crisis import Crisis

shelter_type_pg = PgEnum(
    ShelterType,
    name="shelter_type",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)
shelter_status_pg = PgEnum(
    ShelterStatus,
    name="shelter_status",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)
brazilian_state_pg = PgEnum(
    BrazilianState,
    name="brazilian_state",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class Shelter(Base):
    __tablename__ = "shelters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    # FK constraints for these scope/audit columns live in the migrations.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    responsible_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    address: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    neighborhood: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    city: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    state: Mapped[BrazilianState] = mapped_column(brazilian_state_pg, nullable=False)
    cep: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_requirements: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    occupation: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    shelter_type: Mapped[ShelterType] = mapped_column(shelter_type_pg, nullable=False)
    status: Mapped[ShelterStatus] = mapped_column(
        shelter_status_pg,
        nullable=False,
        server_default="preparing",
    )
    bio: Mapped[str | None] = mapped_column(VARCHAR, nullable=True)
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    crises: Mapped[list["Crisis"]] = relationship(
        "Crisis",
        secondary=CrisesShelters.__table__,
        back_populates="shelters",
    )

    __table_args__ = (
        Index("ix_shelters_status", "status"),
        Index("ix_shelters_verified", "verified"),
        Index("ix_shelters_shelter_type", "shelter_type"),
        Index("ix_shelters_city_state", "city", "state"),
        Index("geo_idx", "latitude", "longitude"),
    )
