import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base


class CrisesShelters(Base):
    """Junction — a shelter can serve multiple crises and vice-versa."""

    __tablename__ = "crises_shelters"

    crisis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "crises.id",
            name="fk_crises_shelters_crisis_id_crises",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    shelter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "shelters.id",
            name="fk_crises_shelters_shelter_id_shelters",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    joined_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
