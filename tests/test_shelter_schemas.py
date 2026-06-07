import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from domain.schemas.enums import ShelterStatus, ShelterType
from domain.shelter.schemas import (
    ShelterCreate,
    ShelterCreateRequest,
    ShelterListItemResponse,
    ShelterRead,
    ShelterSummaryResponse,
    ShelterUpdate,
    ShelterUpdateRequest,
)

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _valid_shelter_payload() -> dict:
    return {
        "organization_id": uuid.uuid4(),
        "responsible_user_id": uuid.uuid4(),
        "verified_by": None,
        "name": "Abrigo Central",
        "address": "Rua Principal, 100",
        "latitude": -23.55,
        "longitude": -46.63,
        "capacity": 100,
        "occupation": 25,
        "shelter_type": ShelterType.INSTITUTIONAL,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    }


def _valid_create_request_payload() -> dict:
    return {
        "name": "Abrigo Central",
        "address": "Rua Principal, 100",
        "latitude": -23.55,
        "longitude": -46.63,
        "capacity": 100,
        "occupation": 25,
        "shelter_type": ShelterType.INSTITUTIONAL,
    }


def test_shelter_create_accepts_valid_data():
    payload = _valid_shelter_payload()

    shelter = ShelterCreate(**payload)

    assert shelter.name == payload["name"]
    assert shelter.occupation == 25
    assert shelter.capacity == 100
    assert "created_by" not in shelter.model_dump()


def test_shelter_create_request_exposes_only_public_fields():
    payload = _valid_create_request_payload()

    shelter = ShelterCreateRequest(**payload)

    assert shelter.model_dump() == payload


def test_shelter_create_request_rejects_administrative_fields():
    payload = {
        **_valid_create_request_payload(),
        "created_by": uuid.uuid4(),
        "responsible_user_id": uuid.uuid4(),
        "verified_by": uuid.uuid4(),
        "verified": True,
        "status": ShelterStatus.ACTIVE,
        "crisis_id": uuid.uuid4(),
    }

    with pytest.raises(ValidationError):
        ShelterCreateRequest(**payload)


def test_shelter_create_rejects_occupation_above_capacity():
    payload = _valid_shelter_payload()
    payload["occupation"] = 101

    with pytest.raises(ValidationError):
        ShelterCreate(**payload)


def test_shelter_create_request_rejects_occupation_above_capacity():
    payload = _valid_create_request_payload()
    payload["occupation"] = 101

    with pytest.raises(ValidationError):
        ShelterCreateRequest(**payload)


def test_shelter_update_accepts_partial_data():
    update = ShelterUpdate(name="Abrigo Atualizado", occupation=40)

    assert update.model_dump(exclude_unset=True) == {
        "name": "Abrigo Atualizado",
        "occupation": 40,
    }


def test_shelter_update_request_rejects_administrative_fields():
    with pytest.raises(ValidationError):
        ShelterUpdateRequest(verified=True)


def test_shelter_read_serializes_from_attributes_without_crisis_id():
    shelter = SimpleNamespace(
        id=uuid.uuid4(),
        **_valid_shelter_payload(),
        created_by=uuid.uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        crisis_id=uuid.uuid4(),
        urgent_needs=["water"],
        severity="high",
        city="Sao Paulo",
        state="SP",
    )

    response = ShelterRead.model_validate(shelter)
    payload = response.model_dump()

    assert "crisis_id" not in payload
    assert "urgent_needs" not in payload
    assert "severity" not in payload
    assert "city" not in payload
    assert "state" not in payload
    assert payload["id"] == shelter.id


def test_shelter_list_and_summary_responses_are_limited():
    shelter = SimpleNamespace(
        id=uuid.uuid4(),
        **_valid_shelter_payload(),
        created_by=uuid.uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        crisis_id=uuid.uuid4(),
        urgent_needs=["water"],
        severity="high",
    )

    list_payload = ShelterListItemResponse.model_validate(shelter).model_dump()
    summary_payload = ShelterSummaryResponse.model_validate(shelter).model_dump()

    assert set(list_payload) == {
        "id",
        "name",
        "address",
        "capacity",
        "occupation",
        "shelter_type",
        "status",
        "verified",
    }
    assert set(summary_payload) == {
        "id",
        "name",
        "address",
        "capacity",
        "occupation",
        "status",
    }
