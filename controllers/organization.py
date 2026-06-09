from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from dependencies.session import get_session
from domain.models.organization import Organization
from domain.registration.schemas import OrganizationSearchResult

router = APIRouter(prefix="/organizations", tags=["organizations"])

_SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/search", response_model=list[OrganizationSearchResult])
def search_organizations(
    session: _SessionDep,
    q: Annotated[str, Query(max_length=200)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[OrganizationSearchResult]:
    stmt = select(Organization).order_by(Organization.name).limit(limit)
    if q:
        stmt = stmt.where(Organization.name.ilike(f"%{q}%"))
    return list(session.scalars(stmt).all())
