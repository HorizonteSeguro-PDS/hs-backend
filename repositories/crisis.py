from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.models.crises_shelters import CrisesShelters
from domain.models.crisis import Crisis
from domain.schemas.enums import BrazilianState
from repositories.base import BaseRepository
from schemas.pagination import PaginationParams


@dataclass(frozen=True)
class CrisisListRow:
    crisis: Crisis
    shelters_count: int


class CrisisRepository(BaseRepository[Crisis]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Crisis)

    def list_paginated(
        self,
        params: PaginationParams,
        *,
        status: CrisisStatus | None = None,
        state: BrazilianState | str | None = None,
        type_: CrisisType | None = None,
    ) -> tuple[list[CrisisListRow], int]:
        stmt = (
            select(Crisis, func.count(CrisesShelters.shelter_id).label("shelters_count"))
            .outerjoin(CrisesShelters, CrisesShelters.crisis_id == Crisis.id)
            .group_by(Crisis.id)
            .order_by(Crisis.created_at.desc())
        )
        count_stmt = select(func.count()).select_from(Crisis)
        stmt = self._apply_filters(stmt, status=status, state=state, type_=type_)
        count_stmt = self._apply_filters(
            count_stmt, status=status, state=state, type_=type_
        )

        rows = self.session.execute(
            stmt.offset(params.offset).limit(params.limit)
        ).all()
        total = self.session.scalar(count_stmt) or 0
        return [
            CrisisListRow(crisis=crisis, shelters_count=shelters_count)
            for crisis, shelters_count in rows
        ], total

    def get_with_shelters(self, crisis_id: UUID) -> Crisis | None:
        stmt = (
            select(Crisis)
            .options(selectinload(Crisis.shelters))
            .where(Crisis.id == crisis_id)
        )
        return self.session.scalar(stmt)

    def _apply_filters(
        self,
        stmt: Select,
        *,
        status: CrisisStatus | None,
        state: BrazilianState | str | None,
        type_: CrisisType | None,
    ) -> Select:
        if status is not None:
            stmt = stmt.where(Crisis.status == status)
        if state is not None:
            stmt = stmt.where(Crisis.state == state)
        if type_ is not None:
            stmt = stmt.where(Crisis.type == type_)
        return stmt
