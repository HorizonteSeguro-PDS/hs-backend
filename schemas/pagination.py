from __future__ import annotations

from math import ceil
from typing import Annotated, Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=10, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)

    @classmethod
    def create(
        cls,
        *,
        items: Sequence[T],
        total: int,
        params: PaginationParams,
    ) -> Page[T]:
        return cls(
            items=list(items),
            total=total,
            page=params.page,
            size=params.size,
            pages=calculate_pages(total=total, size=params.size),
        )


def calculate_pages(*, total: int, size: int) -> int:
    if total <= 0:
        return 0
    return ceil(total / size)


def pagination_params(
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 10,
) -> PaginationParams:
    return PaginationParams(page=page, size=size)
