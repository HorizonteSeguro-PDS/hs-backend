from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.schemas.enums import (
    MovementDirection,
    MovementReason,
    ResourceUnit,
)


# ---------- ResourceCategory ----------


class ResourceCategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    unit: ResourceUnit
    description: str | None = Field(default=None, max_length=500)


class ResourceCategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit: ResourceUnit | None = None
    description: str | None = Field(default=None, max_length=500)


class ResourceCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    unit: ResourceUnit
    description: str | None = None


# ---------- InventoryItem (snapshot atual) ----------


class InventoryItemRead(BaseModel):
    """Snapshot do estoque atual de uma categoria num abrigo."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shelter_id: UUID
    category_id: UUID
    quantity_current: int
    updated_at: datetime


class InventoryItemWithCategoryRead(BaseModel):
    """InventoryItem com a categoria já resolvida — pra exibição."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shelter_id: UUID
    category: ResourceCategoryRead
    quantity_current: int
    updated_at: datetime


# ---------- InventoryMovement ----------


class InventoryMovementCreateRequest(BaseModel):
    """Payload pra registrar entrada ou saída de recurso num abrigo.

    `created_by` vem do JWT, não do body.
    """

    model_config = ConfigDict(extra="forbid")

    category_id: UUID
    direction: MovementDirection
    quantity: int = Field(gt=0, description="Quantidade positiva (>0)")
    reason: MovementReason
    source: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shelter_id: UUID
    category_id: UUID
    direction: MovementDirection
    quantity: int
    reason: MovementReason
    source: str | None = None
    notes: str | None = None
    created_by: UUID
    created_at: datetime


class InventoryMovementWithCategoryRead(BaseModel):
    """Movement com a categoria embutida — pra dashboards."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shelter_id: UUID
    category: ResourceCategoryRead
    direction: MovementDirection
    quantity: int
    reason: MovementReason
    source: str | None = None
    notes: str | None = None
    created_by: UUID
    created_at: datetime


class InventoryMovementRecordedResponse(BaseModel):
    """Resposta do POST /inventory/movements — inclui saldo pós-movimento."""

    model_config = ConfigDict(from_attributes=True)

    movement: InventoryMovementRead
    inventory_after: int = Field(
        description="Saldo de quantity_current DEPOIS desse movimento."
    )
