import uuid
from datetime import datetime

from sqlalchemy import Index, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base


class ShelterStay(Base):
    """One row per check-in at a shelter — preserves movement history.

    When a beneficiary moves between shelters, the current stay gets
    `checked_out_at` set and a new row is inserted with the destination
    shelter and a fresh `checked_in_at`. The current shelter of a beneficiary
    is the row where `checked_out_at IS NULL` (one open stay at a time).
    """

    __tablename__ = "shelter_stays"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    # FK constraints live in the migration.
    beneficiary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    shelter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    checked_in_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    checked_out_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_shelter_stays_beneficiary_id", "beneficiary_id"),
        Index("ix_shelter_stays_shelter_id", "shelter_id"),
        # ix_shelter_stays_open is a partial index — declared in the migration
        # WHERE checked_out_at IS NULL — not expressible via __table_args__.
    )
