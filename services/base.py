from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from domain.errors.http import ResourceNotFoundError
from repositories import BaseRepository
from schemas.pagination import Page, PaginationParams

ModelT = TypeVar("ModelT")


class BaseService(Generic[ModelT]):
    def __init__(self, repository: BaseRepository[ModelT]) -> None:
        self.repository = repository

    def get(self, id_: object) -> ModelT | None:
        return self.repository.get(id_)

    def get_or_raise(self, id_: object) -> ModelT:
        entity = self.get(id_)
        if entity is None:
            raise ResourceNotFoundError()
        return entity

    def list(self, offset: int = 0, limit: int | None = None) -> list[ModelT]:
        return self.repository.list(offset=offset, limit=limit)

    def paginate(self, params: PaginationParams) -> Page[ModelT]:
        items = self.repository.list(offset=params.offset, limit=params.limit)
        total = self.repository.count()
        return Page.create(items=items, total=total, params=params)

    def create(self, instance: ModelT) -> ModelT:
        self.repository.add(instance)
        self.repository.flush()
        self.repository.refresh(instance)
        return instance

    def update(self, id_: object, data: Mapping[str, Any]) -> ModelT:
        entity = self.get_or_raise(id_)
        for field, value in data.items():
            setattr(entity, field, value)
        self.repository.flush()
        self.repository.refresh(entity)
        return entity

    def delete(self, id_: object) -> None:
        entity = self.get_or_raise(id_)
        self.repository.delete(entity)
        self.repository.flush()
