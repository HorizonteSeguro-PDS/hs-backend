import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.errors.http import ResourceNotFoundError
from domain.models.crisis import Crisis
from domain.models.shelter import Shelter
from domain.schemas.enums import (
    BrazilianState,
    SeverityLabel,
    ShelterStatus,
    ShelterType,
)
from repositories import CrisisListRow
from schemas.pagination import PaginationParams
from services import CrisisService
from services.crisis import derive_shelter_severity, severity_int_to_label

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_crisis(
    *,
    name: str = "Enchente Teste",
    status: CrisisStatus = CrisisStatus.ACTIVE,
    severity_initial: int | None = 3,
    severity_calculated: int | None = None,
) -> Crisis:
    return Crisis(
        id=uuid.uuid4(),
        name=name,
        type=CrisisType.FLOOD,
        status=status,
        state=BrazilianState.SP,
        city="Sao Paulo",
        severity_initial=severity_initial,
        severity_calculated=severity_calculated,
        created_by=uuid.uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
    )


def _make_shelter(*, capacity: int = 100, occupation: int = 25) -> Shelter:
    return Shelter(
        id=uuid.uuid4(),
        responsible_user_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        name="Abrigo Central",
        address="Rua Principal, 100",
        city="Sao Paulo",
        state=BrazilianState.SP,
        capacity=capacity,
        occupation=occupation,
        shelter_type=ShelterType.INSTITUTIONAL,
        status=ShelterStatus.ACTIVE,
        verified=True,
    )


# --------------------------------------------------------------------------- #
# severity_int_to_label                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, SeverityLabel.INATIVO),
        (1, SeverityLabel.BAIXA),
        (2, SeverityLabel.MEDIA),
        (3, SeverityLabel.ALTA),
        (None, SeverityLabel.INATIVO),
        (99, SeverityLabel.INATIVO),  # fora da escala -> INATIVO
    ],
)
def test_severity_int_to_label_maps_each_level(value, expected):
    assert severity_int_to_label(value) is expected


# --------------------------------------------------------------------------- #
# derive_shelter_severity (occupation/capacity)                                #
# --------------------------------------------------------------------------- #


def test_derive_shelter_severity_empty_is_inativo():
    assert derive_shelter_severity(0, 100) is SeverityLabel.INATIVO


def test_derive_shelter_severity_low_ratio_is_baixa():
    # 25/100 = 0.25 -> BAIXA
    assert derive_shelter_severity(25, 100) is SeverityLabel.BAIXA


def test_derive_shelter_severity_mid_ratio_is_media():
    # 60/100 = 0.60 -> MÉDIA
    assert derive_shelter_severity(60, 100) is SeverityLabel.MEDIA


def test_derive_shelter_severity_high_ratio_is_alta():
    # 90/100 = 0.90 -> ALTA
    assert derive_shelter_severity(90, 100) is SeverityLabel.ALTA


def test_derive_shelter_severity_capacity_zero_is_inativo():
    # Defensivo — capacidade 0 nao trava com ZeroDivision
    assert derive_shelter_severity(0, 0) is SeverityLabel.INATIVO


# --------------------------------------------------------------------------- #
# CrisisService.list_crises                                                   #
# --------------------------------------------------------------------------- #


def test_list_crises_returns_flat_list_with_label_and_active_flag():
    repository = MagicMock()
    params = PaginationParams(page=1, size=10)
    crisis = _make_crisis(severity_initial=3, status=CrisisStatus.ACTIVE)
    repository.list_paginated.return_value = ([CrisisListRow(crisis, 2)], 1)

    items = CrisisService(repository).list_crises(
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
    assert isinstance(items, list)
    assert len(items) == 1
    item = items[0]
    assert item.name == crisis.name
    assert item.severity is SeverityLabel.ALTA
    assert item.shelters_count == 2
    assert item.active is True
    assert item.start_date is None
    # campos antigos NAO devem mais existir
    dumped = item.model_dump()
    assert "type" not in dumped
    assert "status" not in dumped
    assert "severity_initial" not in dumped
    assert "organization_id" not in dumped


def test_list_crises_marks_closed_as_inactive():
    repository = MagicMock()
    crisis = _make_crisis(status=CrisisStatus.CLOSED, severity_initial=0)
    repository.list_paginated.return_value = ([CrisisListRow(crisis, 0)], 1)

    items = CrisisService(repository).list_crises(PaginationParams(page=1, size=10))

    assert items[0].active is False
    assert items[0].severity is SeverityLabel.INATIVO


def test_list_crises_prefers_calculated_severity_over_initial():
    repository = MagicMock()
    crisis = _make_crisis(severity_initial=1, severity_calculated=3)
    repository.list_paginated.return_value = ([CrisisListRow(crisis, 0)], 1)

    items = CrisisService(repository).list_crises(PaginationParams(page=1, size=10))

    assert items[0].severity is SeverityLabel.ALTA


# --------------------------------------------------------------------------- #
# CrisisService.get_crisis_detail                                              #
# --------------------------------------------------------------------------- #


def test_get_crisis_detail_returns_detail_with_shelter_summaries():
    repository = MagicMock()
    crisis = _make_crisis(severity_initial=3)
    crisis.shelters.append(_make_shelter(capacity=100, occupation=90))
    repository.get_with_shelters.return_value = crisis

    detail = CrisisService(repository).get_crisis_detail(crisis.id)

    repository.get_with_shelters.assert_called_once_with(crisis.id)
    assert detail.id == crisis.id
    assert detail.severity is SeverityLabel.ALTA
    assert detail.active is True
    assert detail.shelters_count == 1
    assert len(detail.shelters) == 1

    shelter = detail.shelters[0]
    assert shelter.name == "Abrigo Central"
    assert shelter.current_occupancy == 90
    assert shelter.capacity == 100
    assert shelter.severity is SeverityLabel.ALTA  # 0.90 -> ALTA
    assert shelter.urgent_needs == []


def test_get_crisis_detail_handles_no_shelters():
    repository = MagicMock()
    crisis = _make_crisis()
    # crisis.shelters fica vazio por default
    repository.get_with_shelters.return_value = crisis

    detail = CrisisService(repository).get_crisis_detail(crisis.id)

    assert detail.shelters == []
    assert detail.shelters_count == 0


def test_get_crisis_detail_raises_when_not_found():
    repository = MagicMock()
    crisis_id = uuid.uuid4()
    repository.get_with_shelters.return_value = None

    with pytest.raises(ResourceNotFoundError):
        CrisisService(repository).get_crisis_detail(crisis_id)

    repository.get_with_shelters.assert_called_once_with(crisis_id)
