import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.errors.http import ResourceNotFoundError
from domain.models.crisis import Crisis
from domain.models.shelter import Shelter
from domain.schemas.enums import BrazilianState, ShelterStatus, ShelterType
from repositories import CrisisListRow
from schemas.pagination import PaginationParams
from services import CrisisService

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_crisis(name: str = "Enchente Teste") -> Crisis:
    crisis = Crisis(
        id=uuid.uuid4(),
        name=name,
        type=CrisisType.FLOOD,
        status=CrisisStatus.ACTIVE,
        state=BrazilianState.SP,
        city="Sao Paulo",
        severity_initial=3,
        severity_calculated=None,
        created_by=uuid.uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
    )
    return crisis


def _make_shelter() -> Shelter:
    return Shelter(
        id=uuid.uuid4(),
        responsible_user_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        name="Abrigo Central",
        address="Rua Principal, 100",
        capacity=100,
        occupation=25,
        shelter_type=ShelterType.INSTITUTIONAL,
        status=ShelterStatus.ACTIVE,
        verified=True,
    )


def test_list_crises_returns_paginated_list_items_with_shelters_count():
    repository = MagicMock()
    params = PaginationParams(page=2, size=1)
    crisis = _make_crisis()
    repository.list_paginated.return_value = ([CrisisListRow(crisis, 3)], 5)

    page = CrisisService(repository).list_crises(
        params,
        status=CrisisStatus.ACTIVE,
        state=BrazilianState.SP,
        type_=CrisisType.FLOOD,
    )

    repository.list_paginated.assert_called_once_with(
        params,
        status=CrisisStatus.ACTIVE,
        state=BrazilianState.SP,
        type_=CrisisType.FLOOD,
    )
    assert page.total == 5
    assert page.page == 2
    assert page.size == 1
    assert page.pages == 5
    assert len(page.items) == 1
    assert page.items[0].name == crisis.name
    assert page.items[0].shelters_count == 3


def test_get_crisis_detail_returns_detail_with_shelter_summaries():
    repository = MagicMock()
    crisis = _make_crisis()
    crisis.shelters.append(_make_shelter())
    repository.get_with_shelters.return_value = crisis

    detail = CrisisService(repository).get_crisis_detail(crisis.id)

    repository.get_with_shelters.assert_called_once_with(crisis.id)
    assert detail.id == crisis.id
    assert len(detail.shelters) == 1
    assert detail.shelters[0].name == "Abrigo Central"


def test_get_crisis_detail_raises_when_not_found():
    repository = MagicMock()
    crisis_id = uuid.uuid4()
    repository.get_with_shelters.return_value = None

    with pytest.raises(ResourceNotFoundError):
        CrisisService(repository).get_crisis_detail(crisis_id)

    repository.get_with_shelters.assert_called_once_with(crisis_id)
