import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.crisis.schemas import (
    CrisisCreate,
    CrisisDetailResponse,
    CrisisListItemResponse,
    ShelterInCrisisResponse,
)
from domain.schemas.enums import BrazilianState, SeverityLabel


# --------------------------------------------------------------------------- #
# CrisisCreate — escala 0-3 (INATIVO/BAIXA/MÉDIA/ALTA)                         #
# --------------------------------------------------------------------------- #


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

    assert crisis.severity_initial == 3  # ALTA = 3 na escala nova
    assert crisis.state == "SP"
    assert crisis.start_date == date(2024, 1, 1)
    assert crisis.status == CrisisStatus.ACTIVE
    assert crisis.type == CrisisType.FLOOD


def test_crisis_create_maps_baixa_to_1():
    crisis = CrisisCreate(
        name="Estiagem",
        severity="baixa",
        state="CE",
        city="Fortaleza",
        type=CrisisType.OTHER,
    )
    assert crisis.severity_initial == 1


def test_crisis_create_maps_media_to_2_with_or_without_accent():
    no_accent = CrisisCreate(
        name="Crise A",
        severity="media",
        state="SP",
        city="Sao Paulo",
        type=CrisisType.FLOOD,
    )
    with_accent = CrisisCreate(
        name="Crise B",
        severity="média",
        state="SP",
        city="Sao Paulo",
        type=CrisisType.FLOOD,
    )
    assert no_accent.severity_initial == 2
    assert with_accent.severity_initial == 2


def test_crisis_create_maps_inativo_to_zero():
    crisis = CrisisCreate(
        name="Crise hibernando",
        severity="inativo",
        state="SP",
        city="Sao Paulo",
        type=CrisisType.OTHER,
    )
    assert crisis.severity_initial == 0


def test_crisis_create_accepts_int_severity_in_range():
    crisis = CrisisCreate(
        name="Crise",
        severity=2,
        state="SP",
        city="Sao Paulo",
        type=CrisisType.FLOOD,
    )
    assert crisis.severity_initial == 2


def test_crisis_create_rejects_int_severity_out_of_range():
    with pytest.raises(ValidationError):
        CrisisCreate(
            name="Crise",
            severity=5,  # antiga "critica" — nao existe mais
            state="SP",
            city="Sao Paulo",
            type=CrisisType.FLOOD,
        )


def test_crisis_create_rejects_unknown_severity_alias():
    with pytest.raises(ValidationError):
        CrisisCreate(
            name="Crise",
            severity="extrema",  # nao mapeia
            state="SP",
            city="Sao Paulo",
            type=CrisisType.FLOOD,
        )


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


def test_crisis_create_severity_initial_field_caps_at_3():
    with pytest.raises(ValidationError):
        CrisisCreate(
            name="Crise",
            type=CrisisType.FLOOD,
            state="SP",
            city="Sao Paulo",
            severity_initial=4,  # ge=0, le=3 agora
        )


# --------------------------------------------------------------------------- #
# CrisisListItemResponse — shape exato que o front pediu                      #
# --------------------------------------------------------------------------- #


def test_crisis_list_item_response_has_only_the_fields_the_front_wants():
    response = CrisisListItemResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "name": "Enchente Teste",
            "severity": SeverityLabel.ALTA,
            "state": "SP",
            "city": "Sao Paulo",
            "start_date": date(2024, 1, 1),
            "shelters_count": 2,
            "active": True,
        }
    )
    payload = response.model_dump()

    assert set(payload) == {
        "id",
        "name",
        "severity",
        "state",
        "city",
        "start_date",
        "shelters_count",
        "active",
    }
    assert payload["severity"] == SeverityLabel.ALTA
    assert payload["active"] is True
    assert payload["shelters_count"] == 2


def test_crisis_list_item_response_serializes_severity_as_string():
    response = CrisisListItemResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "name": "Crise Média",
            "severity": SeverityLabel.MEDIA,
            "state": "SP",
            "city": "Sao Paulo",
            "start_date": None,
            "shelters_count": 0,
            "active": False,
        }
    )
    dumped = response.model_dump(mode="json")
    assert dumped["severity"] == "MÉDIA"


# --------------------------------------------------------------------------- #
# ShelterInCrisisResponse — shelter aninhado em GET /crises/{id}              #
# --------------------------------------------------------------------------- #


def test_shelter_in_crisis_response_uses_current_occupancy_and_urgent_needs():
    response = ShelterInCrisisResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "name": "Abrigo Central",
            "city": "Sao Paulo",
            "state": BrazilianState.SP,
            "urgent_needs": [],
            "capacity": 100,
            "current_occupancy": 25,
            "severity": SeverityLabel.BAIXA,
        }
    )
    payload = response.model_dump()

    assert set(payload) == {
        "id",
        "name",
        "city",
        "state",
        "latitude",
        "longitude",
        "urgent_needs",
        "capacity",
        "current_occupancy",
        "severity",
    }
    assert payload["urgent_needs"] == []
    assert payload["current_occupancy"] == 25
    assert payload["severity"] == SeverityLabel.BAIXA


# --------------------------------------------------------------------------- #
# CrisisDetailResponse — listagem + shelters                                  #
# --------------------------------------------------------------------------- #


def test_crisis_detail_response_includes_shelters_field():
    detail = CrisisDetailResponse.model_validate(
        {
            "id": uuid.uuid4(),
            "name": "Enchente Teste",
            "severity": SeverityLabel.ALTA,
            "state": "SP",
            "city": "Sao Paulo",
            "start_date": None,
            "shelters_count": 1,
            "active": True,
            "shelters": [
                {
                    "id": uuid.uuid4(),
                    "name": "Abrigo Central",
                    "city": "Sao Paulo",
                    "state": BrazilianState.SP,
                    "urgent_needs": [],
                    "capacity": 100,
                    "current_occupancy": 90,
                    "severity": SeverityLabel.ALTA,
                }
            ],
        }
    )

    assert len(detail.shelters) == 1
    assert detail.shelters[0].name == "Abrigo Central"
    assert detail.shelters[0].severity == SeverityLabel.ALTA
    assert detail.active is True
