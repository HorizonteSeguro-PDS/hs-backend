import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.crisis.schemas import CrisisDetailResponse, CrisisListItemResponse
from domain.schemas.enums import ShelterStatus

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_crisis_list_item_response_is_limited_to_listing_fields():
    crisis = SimpleNamespace(
        id=uuid.uuid4(),
        name="Enchente Teste",
        type=CrisisType.FLOOD,
        description="Detalhe interno",
        status=CrisisStatus.ACTIVE,
        state="SP",
        city="Sao Paulo",
        severity_initial=3,
        severity_calculated=None,
        severity_calculated_at=None,
        created_by=uuid.uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        close_reason="Nao deve aparecer",
    )

    response = CrisisListItemResponse.model_validate(crisis)
    payload = response.model_dump()

    assert set(payload) == {
        "id",
        "name",
        "type",
        "status",
        "state",
        "city",
        "severity_initial",
        "severity_calculated",
        "created_at",
    }
    assert "created_by" not in payload
    assert "close_reason" not in payload


def test_crisis_detail_response_uses_shelter_summary_without_recursion():
    shelter = SimpleNamespace(
        id=uuid.uuid4(),
        name="Abrigo Central",
        address="Rua Principal, 100",
        capacity=100,
        occupation=25,
        status=ShelterStatus.ACTIVE,
        crises=[],
    )
    crisis = SimpleNamespace(
        id=uuid.uuid4(),
        name="Enchente Teste",
        type=CrisisType.FLOOD,
        description=None,
        status=CrisisStatus.ACTIVE,
        state="SP",
        city="Sao Paulo",
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
        "capacity",
        "occupation",
        "status",
    }
