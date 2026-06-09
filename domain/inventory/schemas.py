from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.schemas.enums import (
    LotCategory,
    MovementDirection,
    MovementReason,
    ResourceUnit,
)


# ---------- ResourceCategory ----------


class ResourceCategoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    unit: ResourceUnit
    lot_category: LotCategory
    description: str | None = Field(default=None, max_length=500)


class ResourceCategoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    unit: ResourceUnit | None = None
    lot_category: LotCategory | None = None
    description: str | None = Field(default=None, max_length=500)


class ResourceCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    unit: ResourceUnit
    lot_category: LotCategory
    description: str | None = None


# ---------- InventoryItem (snapshot atual) ----------


class InventoryItemRead(BaseModel):
    """Snapshot do estoque atual de uma categoria num abrigo."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shelter_id: UUID
    category_id: UUID
    quantity_current: int
    quantity_max: int | None = None
    updated_at: datetime


class InventoryItemWithCategoryRead(BaseModel):
    """InventoryItem com a categoria já resolvida — pra exibição."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shelter_id: UUID
    category: ResourceCategoryRead
    quantity_current: int
    quantity_max: int | None = None
    updated_at: datetime


class InventoryItemQuantityMaxUpdateRequest(BaseModel):
    """Payload pra setar/limpar o teto de estoque (quantity_max)."""

    model_config = ConfigDict(extra="forbid")

    quantity_max: int | None = Field(
        default=None,
        gt=0,
        description="Teto desejado pro item (>0). NULL limpa o teto.",
    )


# ---------- InventoryMovement ----------


class InventoryMovementCreateRequest(BaseModel):
    """Payload pra registrar entrada ou saída de recurso num abrigo.

    `created_by` vem do JWT, não do body.

    `reason` é opcional: se omitido, default por direção:
      - IN  -> DONATION
      - OUT -> DISTRIBUTION
    O front pode mandar reason explicito (ex: TRANSFER_OUT, ADJUSTMENT)
    quando quiser sobrescrever o default.

    `destination_shelter_id` deve ser preenchido APENAS em transferencias
    pra outro abrigo (direction=OUT, reason=TRANSFER_OUT). O CHECK no banco
    duplica essa amarra como ultima linha de defesa.
    """

    model_config = ConfigDict(extra="forbid")

    category_id: UUID
    direction: MovementDirection
    quantity: int = Field(gt=0, description="Quantidade positiva (>0)")
    reason: MovementReason | None = None
    source: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    destination_shelter_id: UUID | None = None

    @model_validator(mode="after")
    def _default_reason_by_direction(self) -> "InventoryMovementCreateRequest":
        if self.reason is None:
            self.reason = (
                MovementReason.DONATION
                if self.direction == MovementDirection.IN
                else MovementReason.DISTRIBUTION
            )
        return self

    @model_validator(mode="after")
    def _destination_only_on_transfer_out(self) -> "InventoryMovementCreateRequest":
        is_transfer_out = (
            self.direction == MovementDirection.OUT
            and self.reason == MovementReason.TRANSFER_OUT
        )
        if is_transfer_out and self.destination_shelter_id is None:
            raise ValueError(
                "destination_shelter_id is required when reason=transfer_out"
            )
        if not is_transfer_out and self.destination_shelter_id is not None:
            raise ValueError(
                "destination_shelter_id is only allowed when reason=transfer_out"
            )
        return self


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
    destination_shelter_id: UUID | None = None
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
    destination_shelter_id: UUID | None = None
    created_by: UUID
    created_at: datetime


class InventoryMovementRecordedResponse(BaseModel):
    """Resposta do POST /inventory/movements — inclui saldo pós-movimento."""

    model_config = ConfigDict(from_attributes=True)

    movement: InventoryMovementRead
    inventory_after: int = Field(
        description="Saldo de quantity_current DEPOIS desse movimento."
    )


class ShelterSpreadsheetImportResponse(BaseModel):
    shelter_id: UUID
    resources_imported: int
    people_imported: int = 0
    people_skipped: bool = True
    errors: list[str] = Field(default_factory=list)


# ---------- Initial stock (Modal 1: criar tipo novo + primeira entrada) -- #


class InitialStockCategorySpec(BaseModel):
    """Bloco aninhado dentro de InitialStockRequest — define a categoria
    nova que vai ser criada junto com a primeira entrada.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    unit: ResourceUnit
    lot_category: LotCategory
    description: str | None = Field(default=None, max_length=500)


class InitialStockRequest(BaseModel):
    """Payload do POST /shelters/{id}/inventory/initial-stock.

    Cria uma `ResourceCategory` nova + abre o primeiro `InventoryItem` no
    abrigo + grava `InventoryMovement` IN com `reason=donation`, tudo em
    uma transação. Pensado pra o "modal de entrada de recurso especial":
    o gestor registra um item que o sistema nunca viu antes.
    """

    model_config = ConfigDict(extra="forbid")

    category: InitialStockCategorySpec
    quantity: int = Field(
        gt=0, description="Quantidade inicial em estoque (primeira entrada)."
    )
    source: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)


class InitialStockResponse(BaseModel):
    """Tudo que foi criado pela operação atômica."""

    category: ResourceCategoryRead
    item: InventoryItemRead
    movement: InventoryMovementRead
    inventory_after: int = Field(
        ge=0, description="Saldo de quantity_current após a operação."
    )
