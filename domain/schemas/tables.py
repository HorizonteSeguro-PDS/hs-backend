from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from domain.schemas.base import BaseSchema
from domain.schemas.enums import (
    AuditAction,
    AuditEntityType,
    BrazilianState,
    CrisisStatus,
    CrisisType,
    DistributionStatus,
    DonationStatus,
    NotificationType,
    OrganizationType,
    PriorityLevel,
    ResourceUnit,
    RoleScope,
    ShelterNeedStatus,
    ShelterStatus,
    ShelterType,
    TransferType,
    VulnerabilityType,
)


class RoleBase(BaseModel):
    name: str
    scope: RoleScope
    permissions: dict[str, Any] | None = None


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = None
    scope: RoleScope | None = None
    permissions: dict[str, Any] | None = None


class RoleRead(RoleBase, BaseSchema):
    id: UUID


class OrganizationBase(BaseModel):
    name: str
    cnpj: str | None = None
    type: OrganizationType
    contact_email: str | None = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: str | None = None
    cnpj: str | None = None
    type: OrganizationType | None = None
    contact_email: str | None = None


class OrganizationRead(OrganizationBase, BaseSchema):
    id: UUID
    created_at: datetime


class UserBase(BaseModel):
    role_id: UUID
    organization_id: UUID | None = None
    name: str
    email: str
    phone: str | None = None
    verified: bool = False


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    role_id: UUID | None = None
    organization_id: UUID | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    verified: bool | None = None
    last_login_at: datetime | None = None


class UserRead(UserBase, BaseSchema):
    id: UUID
    created_at: datetime
    last_login_at: datetime | None = None


class CrisisBase(BaseModel):
    organization_id: UUID | None = None
    created_by: UUID
    closed_by: UUID | None = None
    name: str
    type: CrisisType
    description: str | None = None
    status: CrisisStatus = CrisisStatus.ACTIVE
    state: BrazilianState
    city: str
    severity_initial: int | None = None
    severity_calculated: int | None = None
    severity_calculated_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None


class CrisisCreate(CrisisBase):
    pass


class CrisisUpdate(BaseModel):
    organization_id: UUID | None = None
    created_by: UUID | None = None
    closed_by: UUID | None = None
    name: str | None = None
    type: CrisisType | None = None
    description: str | None = None
    status: CrisisStatus | None = None
    state: BrazilianState | None = None
    city: str | None = None
    severity_initial: int | None = None
    severity_calculated: int | None = None
    severity_calculated_at: datetime | None = None
    closed_at: datetime | None = None
    close_reason: str | None = None


class CrisisRead(CrisisBase, BaseSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ShelterBase(BaseModel):
    crisis_id: UUID
    organization_id: UUID | None = None
    responsible_user_id: UUID
    created_by: UUID
    verified_by: UUID | None = None
    name: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    capacity: int
    occupation: int = 0
    shelter_type: ShelterType
    status: ShelterStatus = ShelterStatus.PREPARING
    verified: bool = False


class ShelterCreate(ShelterBase):
    pass


class ShelterUpdate(BaseModel):
    crisis_id: UUID | None = None
    organization_id: UUID | None = None
    responsible_user_id: UUID | None = None
    created_by: UUID | None = None
    verified_by: UUID | None = None
    name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    capacity: int | None = None
    occupation: int | None = None
    shelter_type: ShelterType | None = None
    status: ShelterStatus | None = None
    verified: bool | None = None


class ShelterRead(ShelterBase, BaseSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime


class BeneficiaryBase(BaseModel):
    shelter_id: UUID
    name: str
    age: int | None = None
    vulnerability: VulnerabilityType | None = None
    notes: str | None = None
    checked_out_at: datetime | None = None


class BeneficiaryCreate(BeneficiaryBase):
    pass


class BeneficiaryUpdate(BaseModel):
    shelter_id: UUID | None = None
    name: str | None = None
    age: int | None = None
    vulnerability: VulnerabilityType | None = None
    notes: str | None = None
    checked_out_at: datetime | None = None


class BeneficiaryRead(BeneficiaryBase, BaseSchema):
    id: UUID
    checked_in_at: datetime


class ResourceCategoryBase(BaseModel):
    name: str
    unit: ResourceUnit
    description: str | None = None


class ResourceCategoryCreate(ResourceCategoryBase):
    pass


class ResourceCategoryUpdate(BaseModel):
    name: str | None = None
    unit: ResourceUnit | None = None
    description: str | None = None


class ResourceCategoryRead(ResourceCategoryBase, BaseSchema):
    id: UUID


class ShelterNeedBase(BaseModel):
    shelter_id: UUID
    category_id: UUID
    quantity_needed: int
    priority: PriorityLevel = PriorityLevel.MEDIUM
    status: ShelterNeedStatus = ShelterNeedStatus.OPEN


class ShelterNeedCreate(ShelterNeedBase):
    pass


class ShelterNeedUpdate(BaseModel):
    shelter_id: UUID | None = None
    category_id: UUID | None = None
    quantity_needed: int | None = None
    priority: PriorityLevel | None = None
    status: ShelterNeedStatus | None = None


class ShelterNeedRead(ShelterNeedBase, BaseSchema):
    id: UUID
    declared_at: datetime
    updated_at: datetime


class InventoryItemBase(BaseModel):
    shelter_id: UUID
    category_id: UUID
    quantity_current: int = 0


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    shelter_id: UUID | None = None
    category_id: UUID | None = None
    quantity_current: int | None = None


class InventoryItemRead(InventoryItemBase, BaseSchema):
    id: UUID
    updated_at: datetime


class DonationBase(BaseModel):
    crisis_id: UUID
    category_id: UUID
    donor_user_id: UUID
    quantity: int
    status: DonationStatus = DonationStatus.PLEDGED
    note: str | None = None
    received_at: datetime | None = None


class DonationCreate(DonationBase):
    pass


class DonationUpdate(BaseModel):
    crisis_id: UUID | None = None
    category_id: UUID | None = None
    donor_user_id: UUID | None = None
    quantity: int | None = None
    status: DonationStatus | None = None
    note: str | None = None
    received_at: datetime | None = None


class DonationRead(DonationBase, BaseSchema):
    id: UUID
    pledged_at: datetime


class DistributionBase(BaseModel):
    donation_id: UUID | None = None
    origin_shelter_id: UUID | None = None
    destination_shelter_id: UUID
    category_id: UUID
    transfer_type: TransferType
    quantity: int
    status: DistributionStatus = DistributionStatus.PLANNED
    dispatched_at: datetime | None = None
    delivered_at: datetime | None = None


class DistributionCreate(DistributionBase):
    pass


class DistributionUpdate(BaseModel):
    donation_id: UUID | None = None
    origin_shelter_id: UUID | None = None
    destination_shelter_id: UUID | None = None
    category_id: UUID | None = None
    transfer_type: TransferType | None = None
    quantity: int | None = None
    status: DistributionStatus | None = None
    dispatched_at: datetime | None = None
    delivered_at: datetime | None = None


class DistributionRead(DistributionBase, BaseSchema):
    id: UUID


class NotificationBase(BaseModel):
    user_id: UUID
    type: NotificationType
    message: str
    read: bool = False


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    user_id: UUID | None = None
    type: NotificationType | None = None
    message: str | None = None
    read: bool | None = None


class NotificationRead(NotificationBase, BaseSchema):
    id: UUID
    created_at: datetime


class AuditLogBase(BaseModel):
    author_id: UUID
    entity_type: AuditEntityType
    entity_id: UUID
    action: AuditAction
    payload: dict[str, Any] | None = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogUpdate(BaseModel):
    author_id: UUID | None = None
    entity_type: AuditEntityType | None = None
    entity_id: UUID | None = None
    action: AuditAction | None = None
    payload: dict[str, Any] | None = None


class AuditLogRead(AuditLogBase, BaseSchema):
    id: UUID
    created_at: datetime
