import uuid
from datetime import datetime

from sqlalchemy import Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base


class InventoryItem(Base):
    """Snapshot of current stock of a resource category at a shelter.

    NOT a movement log — `inventory_movements` holds the history. This row is
    a derived cache updated by `record_movement`. There is at most one row per
    (shelter_id, category_id) — enforced by the unique index.
    """

    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    # FK constraints live in the migrations.
    shelter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quantity_current: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "shelter_id",
            "category_id",
            name="one_snapshot_per_shelter_category",
        ),
    )
