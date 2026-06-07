from sqlalchemy import select
from sqlalchemy.orm import Session
from domain.models.shelter import Shelter
from repositories.base import BaseRepository
class ShelterRepository(BaseRepository[Shelter]):
     def __init__(self, session: Session) -> None:
         super().__init__(session, Shelter)
     def list(self, offset: int = 0, limit: int | None = None) -> list[Shelter]:
         stmt = (
             select(Shelter)
             .order_by(Shelter.created_at.desc(), Shelter.id)
             .offset(offset)
         )
         if limit is not None:
             stmt = stmt.limit(limit)
         return list(self.session.scalars(stmt))