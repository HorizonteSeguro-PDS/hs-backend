from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.models.inventory_item import InventoryItem
from repositories.base import BaseRepository


class InventoryItemRepository(BaseRepository[InventoryItem]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, InventoryItem)

    def get_for_shelter_category(
        self, *, shelter_id: UUID, category_id: UUID
    ) -> InventoryItem | None:
        stmt = select(InventoryItem).where(
            InventoryItem.shelter_id == shelter_id,
            InventoryItem.category_id == category_id,
        )
        return self.session.scalar(stmt)

    def list_for_shelter(self, *, shelter_id: UUID) -> list[InventoryItem]:
        stmt = (
            select(InventoryItem)
            .where(InventoryItem.shelter_id == shelter_id)
            .order_by(InventoryItem.updated_at.desc())
        )
        return list(self.session.scalars(stmt))
