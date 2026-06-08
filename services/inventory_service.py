"""Inventory service.

Two responsibilities:
  1. `record_movement` — atomic write of (movement row + inventory_items cache),
     rejecting OUT operations that would drive the balance negative.
  2. Read queries over the snapshot + movement history.

Writes are gated to dev + crisis_manager + shelter_manager at the controller
layer; reads to the same set (NOT public, by product decision).
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from domain.inventory.schemas import (
    InventoryItemRead,
    InventoryMovementCreateRequest,
    InventoryMovementRead,
    InventoryMovementRecordedResponse,
)
from domain.models.inventory_item import InventoryItem
from domain.models.inventory_movement import InventoryMovement
from domain.schemas.enums import MovementDirection, MovementReason
from repositories.inventory_item import InventoryItemRepository
from repositories.inventory_movement import InventoryMovementRepository
from repositories.resource_category import ResourceCategoryRepository
from schemas.pagination import Page, PaginationParams


class InsufficientInventoryError(HTTPException):
    """Raised when an OUT movement would drive `quantity_current` negative.

    Mapped to HTTP 400 so the controller can let FastAPI surface it directly.
    """

    def __init__(self, *, requested: int, available: int) -> None:
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "insufficient_inventory",
                "requested": requested,
                "available": available,
            },
        )


class InventoryService:
    """Coordinates movements + inventory snapshot updates within one transaction.

    NOT inheriting BaseService because the workflow doesn't map to plain CRUD —
    every mutation has to touch two tables atomically.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.movements = InventoryMovementRepository(session)
        self.items = InventoryItemRepository(session)
        self.categories = ResourceCategoryRepository(session)

    # --- WRITE: record_movement --- #

    def record_movement(
        self,
        *,
        shelter_id: UUID,
        actor_id: UUID,
        payload: InventoryMovementCreateRequest,
    ) -> InventoryMovementRecordedResponse:
        """Insert a movement row and update the inventory cache atomically.

        Caller is responsible for committing the session. This method only
        flushes — keeps the transaction boundary at the controller layer so
        related audit_event calls can land in the same commit.

        Raises:
          ResourceNotFoundError indirectly if the category doesn't exist
          (caller may want to validate first).
          InsufficientInventoryError if the movement is OUT and would drive
          the balance below zero.
        """
        # Get-or-create the inventory_items cache row for (shelter, category).
        item = self.items.get_for_shelter_category(
            shelter_id=shelter_id, category_id=payload.category_id
        )
        if item is None:
            item = InventoryItem(
                shelter_id=shelter_id,
                category_id=payload.category_id,
                quantity_current=0,
            )
            self.session.add(item)
            self.session.flush()

        # Compute the post-movement balance and refuse if it would go negative.
        if payload.direction == MovementDirection.IN:
            new_balance = item.quantity_current + payload.quantity
        else:  # OUT
            new_balance = item.quantity_current - payload.quantity
            if new_balance < 0:
                raise InsufficientInventoryError(
                    requested=payload.quantity,
                    available=item.quantity_current,
                )

        # Write the movement row (immutable history).
        movement = InventoryMovement(
            shelter_id=shelter_id,
            category_id=payload.category_id,
            direction=payload.direction,
            quantity=payload.quantity,
            reason=payload.reason,
            source=payload.source,
            notes=payload.notes,
            created_by=actor_id,
        )
        self.session.add(movement)

        # Update the cache snapshot.
        item.quantity_current = new_balance
        self.session.flush()
        self.session.refresh(movement)
        self.session.refresh(item)

        return InventoryMovementRecordedResponse(
            movement=InventoryMovementRead.model_validate(movement),
            inventory_after=item.quantity_current,
        )

    # --- READ: snapshot --- #

    def list_inventory_for_shelter(
        self, *, shelter_id: UUID
    ) -> list[InventoryItemRead]:
        items = self.items.list_for_shelter(shelter_id=shelter_id)
        return [InventoryItemRead.model_validate(it) for it in items]

    # --- READ: movements --- #

    def list_movements_for_shelter(
        self,
        params: PaginationParams,
        *,
        shelter_id: UUID,
        category_id: UUID | None = None,
        reason: MovementReason | None = None,
    ) -> Page[InventoryMovementRead]:
        rows, total = self.movements.list_paginated_for_shelter(
            params,
            shelter_id=shelter_id,
            category_id=category_id,
            reason=reason,
        )
        return Page[InventoryMovementRead].create(
            items=[InventoryMovementRead.model_validate(r) for r in rows],
            total=total,
            params=params,
        )
