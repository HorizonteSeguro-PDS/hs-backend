from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def get(self, id_: object) -> ModelT | None:
        return self.session.get(self.model, id_)

    def list(self, offset: int = 0, limit: int | None = None) -> list[ModelT]:
        stmt = select(self.model).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.scalars(stmt))

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(self.model)) or 0

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    def delete(self, instance: ModelT) -> None:
        self.session.delete(instance)

    def flush(self) -> None:
        self.session.flush()

    def refresh(self, instance: ModelT) -> None:
        self.session.refresh(instance)
