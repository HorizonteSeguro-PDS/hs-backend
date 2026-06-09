"""Shape do mega-payload de GET /crises/{id}/operations.

Tudo aqui é response-only — nenhum desses schemas é input. A estrutura
aninhada (crisis → shelters → supplies/resources/people) bate com o JSON
que o front mandou.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.schemas.enums import (
    BrazilianState,
    LotCategory,
    MovementDirection,
    ResourceUnit,
    SeverityLabel,
    SupplyStatus,
    VulnerabilityType,
)


class SupplyResponse(BaseModel):
    """Snapshot atual de um suprimento no abrigo, com status derivado."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    current_quantity: int
    unit: ResourceUnit
    max_capacity: int | None = None
    status: SupplyStatus
    lot_category: LotCategory


class ResourceMovementResponse(BaseModel):
    """Uma linha do log de entrada/saida do abrigo.

    `destined_to` so vem populado em transferencias pra outro abrigo (OUT +
    reason=TRANSFER_OUT). Nesse caso é o NOME do abrigo destinatario, nao o id.
    """

    created_at: datetime
    type: MovementDirection
    category: LotCategory
    name: str
    quantity: int
    unit: ResourceUnit
    destined_to: str | None = None


class PersonResponse(BaseModel):
    """Pessoa ATUALMENTE no abrigo (shelter_stay aberto)."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    age: int | None = None
    vulnerabilities: VulnerabilityType | None = None
    cpf: str | None = None


class ShelterOperationsResponse(BaseModel):
    """Bloco por-abrigo do dashboard. Cada um traz overview + recursos + pessoas."""

    id: UUID
    name: str
    city: str
    state: BrazilianState
    severity: SeverityLabel
    capacity: int
    current_occupancy: int
    relative_occupation: float = Field(
        ge=0,
        description="occupation/capacity (0..1+). Pode passar de 1 se houver superlotacao.",
    )
    active_managers: int = Field(
        ge=0,
        description="Quantidade de users com scope em users_shelters pra esse abrigo.",
    )
    supplies: list[SupplyResponse] = Field(default_factory=list)
    resources: list[ResourceMovementResponse] = Field(default_factory=list)
    people: list[PersonResponse] = Field(default_factory=list)


class CrisisOperationsResponse(BaseModel):
    """Resposta de GET /crises/{id}/operations — mega-payload do dashboard."""

    id: UUID
    name: str
    city: str
    shelters: list[ShelterOperationsResponse] = Field(default_factory=list)
