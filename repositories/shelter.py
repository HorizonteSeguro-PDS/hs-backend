from sqlalchemy.orm import Session

from domain.models.shelter import Shelter
from repositories.base import BaseRepository


class ShelterRepository(BaseRepository[Shelter]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Shelter)
