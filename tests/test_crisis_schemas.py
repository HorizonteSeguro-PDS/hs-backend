import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.crisis.schemas import (
    CrisisCreate,
    CrisisDetailResponse,
    CrisisListItemResponse,
)
from domain.schemas.enums import BrazilianState, ShelterStatus

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_crisis_list_item_response_is_limited_to_listing_fields():
    organization_id = uuid.uuid4()
    crisis = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id,
        name="Enchente Teste",
        type=CrisisType.FLOOD,
        description="Detalhe interno",
        status=CrisisStatus.ACTIVE,
        state="SP",
        city="Sao Paulo",
        start_date=date(2024, 1, 1),
        severity_initial=3,
        severity_calculated=None,
        severity_calculated_at=None,
        created_by=uuid.uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        close_reason="Nao deve aparecer",
        shelters_count=2,
    )

    response = CrisisListItemResponse.model_validate(crisis)
    payload = response.model_dump()

    assert set(payload) == {
        "id",
        "organization_id",
        "name",
        "type",
        "status",
        "state",
        "city",
        "start_date",
        "severity_initial",
        "severity_calculated",
        "created_at",
        "shelters_count",
    }
    assert "created_by" not in payload
    assert "close_reason" not in payload
    assert payload["organization_id"] == organization_id
    assert payload["start_date"] == date(2024, 1, 1)
    assert payload["shelters_count"] == 2


def test_crisis_create_accepts_modal_payload_aliases():
    crisis = CrisisCreate(
        name="Sao Paulo Crisis",
        severity="ALTA",
        state="Sao Paulo",
        city="Sao Paulo",
        start_date="2024-01-01",
        status="ATIVA",
        type="FLOOD",
    )

    assert crisis.severity_initial == 4
    assert crisis.state == "SP"
    assert crisis.start_date == date(2024, 1, 1)
    assert crisis.status == CrisisStatus.ACTIVE
    assert crisis.type == CrisisType.FLOOD


def test_crisis_create_rejects_organization_id_in_request_body():
    with pytest.raises(ValidationError):
        CrisisCreate(
            name="Sao Paulo Crisis",
            type="flood",
            state="SP",
            city="Sao Paulo",
            organization_id=uuid.uuid4(),
        )


def test_crisis_create_strips_type_and_uppercases_uf():
    crisis = CrisisCreate(
        name="Enchente Teste",
        type=" FLOOD ",
        state="sp",
        city="Sao Paulo",
    )

    assert crisis.type == CrisisType.FLOOD
    assert crisis.state == "SP"


def test_crisis_detail_response_uses_shelter_summary_without_recursion():
    shelter = SimpleNamespace(
        id=uuid.uuid4(),
        name="Abrigo Central",
        address="Rua Principal, 100",
        city="Sao Paulo",
        state=BrazilianState.SP,
        capacity=100,
        occupation=25,
        status=ShelterStatus.ACTIVE,
        crises=[],
    )
    crisis = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=None,
        name="Enchente Teste",
        type=CrisisType.FLOOD,
        description=None,
        status=CrisisStatus.ACTIVE,
        state="SP",
        city="Sao Paulo",
        start_date=None,
        severity_initial=3,
        severity_calculated=None,
        severity_calculated_at=None,
        created_by=uuid.uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        closed_at=None,
        closed_by=None,
        close_reason=None,
        shelters=[shelter],
    )

    response = CrisisDetailResponse.model_validate(crisis)
    payload = response.model_dump()

    assert len(payload["shelters"]) == 1
    assert set(payload["shelters"][0]) == {
        "id",
        "name",
        "address",
        "city",
        "state",
        "capacity",
        "occupation",
        "status",
    }
