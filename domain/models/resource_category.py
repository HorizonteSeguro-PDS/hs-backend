import uuid

from sqlalchemy import VARCHAR, Enum as PgEnum, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from domain.schemas.enums import ResourceUnit
from utils.database import Base

resource_unit_pg = PgEnum(
    ResourceUnit,
    name="resource_unit",
    create_type=False,
    values_callable=lambda obj: [e.value for e in obj],
)


class ResourceCategory(Base):
    """Catálogo de tipos de recurso (cobertor, água, kit médico...).

    Shared across all shelters/crises — one row per kind of item the platform
    knows how to track.
    """

    __tablename__ = "resource_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(VARCHAR, nullable=False)
    unit: Mapped[ResourceUnit] = mapped_column(resource_unit_pg, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("name", name="uq_resource_categories_name"),)
