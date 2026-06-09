"""Tests do filtro lot_category em GET /resource-categories e do default
de `reason` em InventoryMovementCreateRequest (modal 2).
"""

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.inventory.schemas import InventoryMovementCreateRequest
from domain.models.resource_category import ResourceCategory
from domain.schemas.enums import (
    LotCategory,
    MovementDirection,
    MovementReason,
    ResourceUnit,
)
from repositories.resource_category import ResourceCategoryRepository


def _setup_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    ResourceCategory.__table__.create(engine)
    return Session(engine)


def _seed(session: Session, name: str, lot_category: LotCategory) -> ResourceCategory:
    cat = ResourceCategory(
        id=uuid.uuid4(),
        name=name,
        unit=ResourceUnit.UNIDADE,
        lot_category=lot_category,
    )
    session.add(cat)
    session.commit()
    return cat


# --------------------------------------------------------------------------- #
# Filtro lot_category no repository                                           #
# --------------------------------------------------------------------------- #


def test_list_by_lot_category_returns_only_matching_bucket():
    with _setup_session() as session:
        _seed(session, "cobertor", LotCategory.ESSENCIAIS)
        _seed(session, "alimento", LotCategory.ESSENCIAIS)
        _seed(session, "medicamento", LotCategory.SAUDE)
        _seed(session, "voluntario", LotCategory.OPERACAO)

        repo = ResourceCategoryRepository(session)
        essenciais = repo.list_by_lot_category(LotCategory.ESSENCIAIS)
        saude = repo.list_by_lot_category(LotCategory.SAUDE)
        animais = repo.list_by_lot_category(LotCategory.ANIMAIS)

        assert {c.name for c in essenciais} == {"cobertor", "alimento"}
        assert [c.name for c in saude] == ["medicamento"]
        assert animais == []


def test_list_by_lot_category_orders_alphabetically():
    with _setup_session() as session:
        _seed(session, "zorro", LotCategory.ESSENCIAIS)
        _seed(session, "abc", LotCategory.ESSENCIAIS)
        _seed(session, "meio", LotCategory.ESSENCIAIS)

        repo = ResourceCategoryRepository(session)
        items = repo.list_by_lot_category(LotCategory.ESSENCIAIS)
        assert [c.name for c in items] == ["abc", "meio", "zorro"]


# --------------------------------------------------------------------------- #
# Default reason em InventoryMovementCreateRequest (modal 2)                  #
# --------------------------------------------------------------------------- #


def test_default_reason_for_in_is_donation():
    payload = InventoryMovementCreateRequest(
        category_id=uuid.uuid4(),
        direction=MovementDirection.IN,
        quantity=10,
    )
    assert payload.reason == MovementReason.DONATION


def test_default_reason_for_out_is_distribution():
    payload = InventoryMovementCreateRequest(
        category_id=uuid.uuid4(),
        direction=MovementDirection.OUT,
        quantity=10,
    )
    assert payload.reason == MovementReason.DISTRIBUTION


def test_explicit_reason_overrides_default():
    payload = InventoryMovementCreateRequest(
        category_id=uuid.uuid4(),
        direction=MovementDirection.IN,
        quantity=10,
        reason=MovementReason.ADJUSTMENT,
    )
    assert payload.reason == MovementReason.ADJUSTMENT


def test_transfer_out_default_does_not_apply():
    """Quando o front manda reason=TRANSFER_OUT explicitamente, ele tem que
    mandar destination_shelter_id também (regra existente)."""
    import pytest

    with pytest.raises(ValueError, match="destination_shelter_id"):
        InventoryMovementCreateRequest(
            category_id=uuid.uuid4(),
            direction=MovementDirection.OUT,
            quantity=10,
            reason=MovementReason.TRANSFER_OUT,
        )
