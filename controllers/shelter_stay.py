"""POST /shelters/{shelter_id}/check-ins  — registra entrada de pessoa
POST /shelters/{shelter_id}/check-outs — registra saida de pessoa

NAO é publico (mexe com CPF). Requer JWT com dev / crisis_manager /
shelter_manager (mesmas roles que escrevem inventory_movements).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.shelter_stay.schemas import (
    CheckInRequest,
    CheckInResponse,
    CheckOutRequest,
    CheckOutResponse,
)
from services.shelter_stay_service import ShelterStayService


router = APIRouter(prefix="/shelters", tags=["shelter-stays"])

_WriteDep = Annotated[
    CurrentUser,
    Depends(require_role("dev", "crisis_manager", "shelter_manager")),
]
_SessionDep = Annotated[Session, Depends(get_session)]


@router.post(
    "/{shelter_id}/check-ins",
    response_model=CheckInResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "missing/invalid bearer token"},
        403: {"description": "role not authorized"},
        404: {"description": "shelter not found"},
        409: {
            "description": (
                "shelter full OR beneficiary already sheltered elsewhere "
                "(see detail.error)"
            )
        },
    },
)
def check_in(
    shelter_id: UUID,
    payload: CheckInRequest,
    session: _SessionDep,
    _user: _WriteDep,
) -> CheckInResponse:
    """Registra entrada de uma pessoa no abrigo.

    Comportamento:
      - get-or-create beneficiario por CPF (campos opcionais sao reconciliados
        se a pessoa ja existir);
      - bloqueia (409) se a pessoa ja tem stay aberto em algum abrigo;
      - bloqueia (409) se o abrigo esta cheio (occupation == capacity);
      - abre um novo stay e incrementa Shelter.occupation atomicamente.
    """
    result = ShelterStayService(session).check_in(
        shelter_id=shelter_id, payload=payload
    )
    session.commit()
    return result


@router.post(
    "/{shelter_id}/check-outs",
    response_model=CheckOutResponse,
    responses={
        401: {"description": "missing/invalid bearer token"},
        403: {"description": "role not authorized"},
        404: {
            "description": (
                "shelter / beneficiary nao encontrado OU nao ha stay aberto"
            )
        },
        422: {"description": "payload sem cpf nem beneficiary_id"},
    },
)
def check_out(
    shelter_id: UUID,
    payload: CheckOutRequest,
    session: _SessionDep,
    _user: _WriteDep,
) -> CheckOutResponse:
    """Registra saida da pessoa do abrigo (fecha o stay aberto)."""
    result = ShelterStayService(session).check_out(
        shelter_id=shelter_id, payload=payload
    )
    session.commit()
    return result
