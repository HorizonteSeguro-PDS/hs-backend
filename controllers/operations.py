"""GET /crises/{crisis_id}/operations — mega-payload do dashboard do gestor.

NAO é publico: contem CPF (PII). Requer JWT com pelo menos um dos papeis
dev / crisis_manager / shelter_manager. Filtro por organization_id aplicado
no service (dev passa por cima).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.operations.schemas import CrisisOperationsResponse
from services.operations import OperationsService


router = APIRouter(prefix="/crises", tags=["crises"])

_AuthDep = Annotated[
    CurrentUser, Depends(require_role("dev", "crisis_manager", "shelter_manager"))
]
_SessionDep = Annotated[Session, Depends(get_session)]


@router.get(
    "/{crisis_id}/operations",
    response_model=CrisisOperationsResponse,
    responses={
        401: {"description": "missing/invalid bearer token"},
        403: {"description": "role not authorized"},
        404: {"description": "crisis not found"},
    },
)
def get_crisis_operations(
    crisis_id: UUID,
    session: _SessionDep,
    user: _AuthDep,
) -> CrisisOperationsResponse:
    """Mega-payload do dashboard de gestor de abrigos.

    Estrutura: crisis -> shelters[] -> {supplies, resources, people}.

    Scoping (no service):
      - dev: ve todos shelters
      - crisis_manager / shelter_manager: ve so os shelters da propria org
    """
    return OperationsService(session).get_crisis_operations(crisis_id, user)
