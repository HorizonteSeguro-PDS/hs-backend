"""GET /crises/{crisis_id}/operations — mega-payload do dashboard do gestor.

PUBLICO (não exige token). O front controla visibilidade de botões de
gerenciamento (criar movement / fazer check-in / etc) por role, mas a
LEITURA do dashboard fica aberta — bate com o painel de transparência.

ATENÇÃO: o payload inclui CPF dos beneficiários (PII). Se isso passar a
ser um problema (LGPD), considere:
  - mascarar CPF no array `people` quando não tem auth, OU
  - omitir `people` completamente em chamadas anônimas, OU
  - voltar a exigir token só pra `people`.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies.session import get_session
from domain.operations.schemas import CrisisOperationsResponse
from services.operations import OperationsService


router = APIRouter(prefix="/crises", tags=["crises"])

_SessionDep = Annotated[Session, Depends(get_session)]


@router.get(
    "/{crisis_id}/operations",
    response_model=CrisisOperationsResponse,
    responses={
        404: {"description": "crisis not found"},
    },
)
def get_crisis_operations(
    crisis_id: UUID,
    session: _SessionDep,
) -> CrisisOperationsResponse:
    """Mega-payload do dashboard de gestor de abrigos — público.

    Estrutura: crisis -> shelters[] -> {supplies, resources, people}.
    """
    return OperationsService(session).get_crisis_operations(crisis_id)
