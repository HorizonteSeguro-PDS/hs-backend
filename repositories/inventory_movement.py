from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.models.inventory_movement import InventoryMovement
from domain.schemas.enums import MovementReason
from repositories.base import BaseRepository
from schemas.pagination import PaginationParams


class InventoryMovementRepository(BaseRepository[InventoryMovement]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, InventoryMovement)

    def list_paginated_for_shelter(
        self,
        params: PaginationParams,
        *,
        shelter_id: UUID,
        category_id: UUID | None = None,
        reason: MovementReason | None = None,
    ) -> tuple[list[InventoryMovement], int]:
        stmt = (
            select(InventoryMovement)
            .where(InventoryMovement.shelter_id == shelter_id)
            .order_by(InventoryMovement.created_at.desc())
        )
        count_stmt = (
            select(func.count())
            .select_from(InventoryMovement)
            .where(InventoryMovement.shelter_id == shelter_id)
        )

        if category_id is not None:
            stmt = stmt.where(InventoryMovement.category_id == category_id)
            count_stmt = count_stmt.where(InventoryMovement.category_id == category_id)
        if reason is not None:
            stmt = stmt.where(InventoryMovement.reason == reason)
            count_stmt = count_stmt.where(InventoryMovement.reason == reason)

        rows = list(
            self.session.scalars(stmt.offset(params.offset).limit(params.limit))
        )
        total = self.session.scalar(count_stmt) or 0
        return rows, total
