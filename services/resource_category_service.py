from uuid import UUID

from domain.errors.http import ResourceAlreadyExists, ResourceNotFoundError
from domain.inventory.schemas import (
    ResourceCategoryCreateRequest,
    ResourceCategoryRead,
    ResourceCategoryUpdateRequest,
)
from domain.models.resource_category import ResourceCategory
from repositories.resource_category import ResourceCategoryRepository
from services.base import BaseService


class ResourceCategoryService(BaseService[ResourceCategory]):
    """Curated taxonomy of resource types — shared across all shelters/crises.

    Write operations are gated to dev + crisis_manager at the controller layer;
    this service stays decoupled from auth concerns.
    """

    def __init__(self, repository: ResourceCategoryRepository) -> None:
        super().__init__(repository)
        self.repository = repository

    # --- queries --- #

    def list_all(self) -> list[ResourceCategoryRead]:
        items = self.repository.list()
        return [ResourceCategoryRead.model_validate(it) for it in items]

    def search(self, query: str, *, limit: int = 20) -> list[ResourceCategoryRead]:
        items = self.repository.search(query, limit=limit)
        return [ResourceCategoryRead.model_validate(it) for it in items]

    def get(self, category_id: UUID) -> ResourceCategoryRead:
        category = self.repository.get(category_id)
        if category is None:
            raise ResourceNotFoundError("resource category not found")
        return ResourceCategoryRead.model_validate(category)

    # --- mutations --- #

    def create(self, payload: ResourceCategoryCreateRequest) -> ResourceCategoryRead:
        if self.repository.get_by_name(payload.name) is not None:
            raise ResourceAlreadyExists(
                f"resource category with name '{payload.name}' already exists"
            )
        category = ResourceCategory(
            name=payload.name,
            unit=payload.unit,
            description=payload.description,
        )
        self.repository.add(category)
        self.repository.flush()
        self.repository.refresh(category)
        return ResourceCategoryRead.model_validate(category)

    def update(
        self, category_id: UUID, payload: ResourceCategoryUpdateRequest
    ) -> ResourceCategoryRead:
        category = self.repository.get(category_id)
        if category is None:
            raise ResourceNotFoundError("resource category not found")

        updates = payload.model_dump(exclude_unset=True)
        if "name" in updates and updates["name"] != category.name:
            existing = self.repository.get_by_name(updates["name"])
            if existing is not None and existing.id != category_id:
                raise ResourceAlreadyExists(
                    f"resource category with name '{updates['name']}' already exists"
                )
        for field, value in updates.items():
            setattr(category, field, value)
        self.repository.flush()
        self.repository.refresh(category)
        return ResourceCategoryRead.model_validate(category)
