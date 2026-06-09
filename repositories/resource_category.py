from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from domain.models.resource_category import ResourceCategory
from domain.schemas.enums import LotCategory
from repositories.base import BaseRepository


class ResourceCategoryRepository(BaseRepository[ResourceCategory]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ResourceCategory)

    def list_by_lot_category(self, lot_category: LotCategory) -> list[ResourceCategory]:
        """Todas as categorias de um bucket (Essenciais/Saude/etc), ordenadas por nome."""
        stmt = (
            select(ResourceCategory)
            .where(ResourceCategory.lot_category == lot_category)
            .order_by(ResourceCategory.name)
        )
        return list(self.session.scalars(stmt))

    def search(self, query: str, *, limit: int = 20) -> list[ResourceCategory]:
        """Substring match in name/description — used by the frontend search-and-add UX."""
        like = f"%{query}%"
        stmt = (
            select(ResourceCategory)
            .where(
                or_(
                    ResourceCategory.name.ilike(like),
                    ResourceCategory.description.ilike(like),
                )
            )
            .order_by(ResourceCategory.name)
            .limit(limit)
        )
        return list(self.session.scalars(stmt))

    def get_by_name(self, name: str) -> ResourceCategory | None:
        stmt = select(ResourceCategory).where(ResourceCategory.name == name)
        return self.session.scalar(stmt)
