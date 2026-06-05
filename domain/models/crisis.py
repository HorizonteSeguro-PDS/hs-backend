import uuid
from datetime import datetime

from sqlalchemy import (
    VARCHAR,
    CheckConstraint,
    Enum as PgEnum,
    Index,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain.crisis.enums import CrisisStatus, CrisisType
from utils.database import Base

crisis_type_pg = PgEnum(
    CrisisType,
    name="crisis_type",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)
crisis_status_pg = PgEnum(
    CrisisStatus,
    name="crisis_status",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class Crisis(Base):
    __tablename__ = "crises"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    type: Mapped[CrisisType] = mapped_column(crisis_type_pg, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CrisisStatus] = mapped_column(
        crisis_status_pg,
        nullable=False,
        server_default="active",
    )
    state: Mapped[str] = mapped_column(VARCHAR(2), nullable=False)
    city: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    severity_initial: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    severity_calculated: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    severity_calculated_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # TODO: add FK to users(id) once users table exists
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    # TODO: add FK to users(id) once users table exists
    closed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(severity_initial IS NULL OR (severity_initial >= 1 AND severity_initial <= 5))",
            name="ck_crises_severity_initial",
        ),
        CheckConstraint(
            "(severity_calculated IS NULL OR (severity_calculated >= 1 AND severity_calculated <= 5))",
            name="ck_crises_severity_calculated",
        ),
        Index("ix_crises_state_city", "state", "city"),
        Index("ix_crises_status", "status"),
        # ix_crises_created_at is created as DESC in the migration via raw DDL
    )
