import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from domain.errors.http import ResourceNotFoundError
from domain.models.shelter import Shelter
from domain.schemas.enums import BrazilianState, ShelterStatus, ShelterType
from domain.shelter.schemas import (
    ShelterCreateRequest,
    ShelterRead,
    ShelterUpdateRequest,
)
from schemas.pagination import PaginationParams
from services import ShelterService

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_shelter(**kwargs) -> Shelter:
    shelter = Shelter(
        id=kwargs.get("id", uuid.uuid4()),
        organization_id=kwargs.get("organization_id"),
        responsible_user_id=kwargs.get("responsible_user_id", uuid.uuid4()),
        created_by=kwargs.get("created_by", uuid.uuid4()),
        verified_by=kwargs.get("verified_by"),
        name=kwargs.get("name", "Abrigo Central"),
        address=kwargs.get("address", "Rua Principal, 100"),
        neighborhood=kwargs.get("neighborhood", "Centro"),
        city=kwargs.get("city", "Sao Paulo"),
        state=kwargs.get("state", BrazilianState.SP),
        cep=kwargs.get("cep", "01001-000"),
        latitude=kwargs.get("latitude", -23.55),
        longitude=kwargs.get("longitude", -46.63),
        capacity=kwargs.get("capacity", 100),
        occupation=kwargs.get("occupation", 25),
        shelter_type=kwargs.get("shelter_type", ShelterType.INSTITUTIONAL),
        status=kwargs.get("status", ShelterStatus.ACTIVE),
        verified=kwargs.get("verified", True),
    )
    shelter.created_at = kwargs.get("created_at", _NOW)
    shelter.updated_at = kwargs.get("updated_at", _NOW)
    return shelter


def _create_payload() -> ShelterCreateRequest:
    return ShelterCreateRequest(
        name="Abrigo Central",
        address="Rua Principal, 100",
        city="Sao Paulo",
        state=BrazilianState.SP,
        capacity=100,
        occupation=25,
        shelter_type=ShelterType.INSTITUTIONAL,
    )


def test_list_shelters_returns_paginated_list_items():
    repository = MagicMock()
    repository.list.return_value = [_make_shelter()]
    repository.count.return_value = 1
    service = ShelterService(repository)

    page = service.list_shelters(PaginationParams(page=1, size=10))

    repository.list.assert_called_once_with(offset=0, limit=10)
    repository.count.assert_called_once_with()
    assert page.total == 1
    assert page.items[0].name == "Abrigo Central"
    assert not isinstance(page.items[0], Shelter)


def test_get_shelter_returns_read_schema_or_raises():
    shelter = _make_shelter()
    repository = MagicMock()
    repository.get.return_value = shelter
    service = ShelterService(repository)

    detail = service.get_shelter(shelter.id)

    assert isinstance(detail, ShelterRead)
    assert detail.id == shelter.id

    repository.get.return_value = None
    with pytest.raises(ResourceNotFoundError):
        service.get_shelter(uuid.uuid4())


def test_create_shelter_fills_created_by_from_authenticated_user():
    repository = MagicMock()
    service = ShelterService(repository)
    user_id = uuid.uuid4()

    created = service.create_shelter(_create_payload(), created_by=user_id)

    repository.add.assert_called_once()
    repository.flush.assert_called_once_with()
    repository.refresh.assert_called_once_with(created)
    assert created.created_by == user_id
    assert created.responsible_user_id == user_id
    assert created.organization_id is None
    assert created.verified is False
    assert created.verified_by is None
    assert created.status == ShelterStatus.PREPARING


def test_update_shelter_updates_only_payload_fields():
    shelter = _make_shelter(name="Abrigo Antigo", occupation=10)
    repository = MagicMock()
    repository.get.return_value = shelter
    service = ShelterService(repository)

    updated = service.update_shelter(
        shelter.id,
        ShelterUpdateRequest(name="Abrigo Novo", occupation=40),
    )

    assert updated.name == "Abrigo Novo"
    assert updated.occupation == 40
    assert updated.address == "Rua Principal, 100"
    repository.flush.assert_called_once_with()
    repository.refresh.assert_called_once_with(shelter)


def test_delete_shelter_delegates_without_commit():
    shelter = _make_shelter()
    repository = MagicMock()
    repository.get.return_value = shelter
    service = ShelterService(repository)

    service.delete_shelter(shelter.id)

    repository.delete.assert_called_once_with(shelter)
    repository.flush.assert_called_once_with()
    repository.commit.assert_not_called()
