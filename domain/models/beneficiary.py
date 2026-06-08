import uuid

from sqlalchemy import VARCHAR, Enum as PgEnum, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain.schemas.enums import VulnerabilityType
from utils.database import Base

vulnerability_type_pg = PgEnum(
    VulnerabilityType,
    name="vulnerability_type",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class Beneficiary(Base):
    """The canonical record of a person who has been or is sheltered.

    Stay history (which shelter they're at, when they checked in/out) lives in
    `shelter_stays` — one row per check-in. The current shelter is derived
    from the most recent stay with `checked_out_at IS NULL`.
    """

    __tablename__ = "beneficiaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    # FK constraints live in the migrations.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    cpf: Mapped[str | None] = mapped_column(VARCHAR(14), nullable=True)
    name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vulnerability: Mapped[VulnerabilityType | None] = mapped_column(
        vulnerability_type_pg, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_beneficiaries_vulnerability", "vulnerability"),
        Index("ix_beneficiaries_user_id", "user_id"),
        # uq_beneficiaries_cpf is a partial unique index — declared in the
        # migration (where cpf IS NOT NULL) rather than via __table_args__.
    )
