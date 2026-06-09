import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Enum as PgEnum,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain.schemas.enums import MovementDirection, MovementReason
from utils.database import Base

movement_direction_pg = PgEnum(
    MovementDirection,
    name="movement_direction",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)
movement_reason_pg = PgEnum(
    MovementReason,
    name="movement_reason",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class InventoryMovement(Base):
    """One entry/exit event on a shelter's stock of a resource category.

    Immutable — corrections are themselves new rows with reason='adjustment'.
    This is the source-of-truth that drives the movement dashboard and is also
    what `inventory_items.quantity_current` is derived from.

    `destination_shelter_id` é setado APENAS quando reason='transfer_out' AND
    direction='out' — identifica o abrigo destinatario da transferencia. CHECK
    no banco (ck_inventory_movements_destination_only_on_transfer_out) garante
    essa amarra.
    """

    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    shelter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    direction: Mapped[MovementDirection] = mapped_column(
        movement_direction_pg, nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[MovementReason] = mapped_column(movement_reason_pg, nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_shelter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "shelters.id",
            name="fk_inventory_movements_destination_shelter_id_shelters",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            name="fk_inventory_movements_created_by_users",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_inventory_movements_quantity_positive",
        ),
        CheckConstraint(
            "("
            "(direction = 'out' AND reason = 'transfer_out' "
            " AND destination_shelter_id IS NOT NULL)"
            " OR ("
            "  (direction <> 'out' OR reason <> 'transfer_out') "
            "  AND destination_shelter_id IS NULL"
            " )"
            ")",
            name="ck_inventory_movements_destination_only_on_transfer_out",
        ),
        Index("ix_inventory_movements_shelter_id", "shelter_id"),
        Index(
            "ix_inventory_movements_shelter_created_at",
            "shelter_id",
            "created_at",
        ),
        Index("ix_inventory_movements_category_id", "category_id"),
        Index("ix_inventory_movements_created_by", "created_by"),
        Index(
            "ix_inventory_movements_destination_shelter_id",
            "destination_shelter_id",
        ),
    )
