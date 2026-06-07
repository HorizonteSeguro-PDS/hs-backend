import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.crisis.enums import CrisisStatus, CrisisType
from domain.errors.http import ResourceNotFoundError
from domain.models.crises_shelters import CrisesShelters
from domain.models.crisis import Crisis
from domain.models.shelter import Shelter
from domain.schemas.enums import BrazilianState
from repositories import BaseRepository
from schemas.pagination import PaginationParams
from services import BaseService


def _make_crisis(name: str) -> Crisis:
    return Crisis(
        id=uuid.uuid4(),
        name=name,
        type=CrisisType.FLOOD,
        status=CrisisStatus.ACTIVE,
        state=BrazilianState.SP,
        city="Sao Paulo",
        created_by=uuid.uuid4(),
    )


def _create_tables(engine) -> None:
    for table in (Crisis.__table__, Shelter.__table__, CrisesShelters.__table__):
        table.create(engine)


def test_base_service_get_and_get_or_raise():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        service = BaseService(BaseRepository(session, Crisis))
        crisis = service.create(_make_crisis("Enchente Teste"))

        assert service.get(crisis.id) == crisis
        assert service.get_or_raise(crisis.id) == crisis
        assert service.get(uuid.uuid4()) is None
        with pytest.raises(ResourceNotFoundError):
            service.get_or_raise(uuid.uuid4())


def test_base_service_list_and_paginate():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        service = BaseService(BaseRepository(session, Crisis))
        for crisis in [
            _make_crisis("Crise 1"),
            _make_crisis("Crise 2"),
            _make_crisis("Crise 3"),
        ]:
            service.create(crisis)

        assert len(service.list()) == 3
        assert len(service.list(offset=1)) == 2
        assert len(service.list(offset=1, limit=1)) == 1

        page = service.paginate(PaginationParams(page=2, size=2))

        assert len(page.items) == 1
        assert page.total == 3
        assert page.page == 2
        assert page.size == 2
        assert page.pages == 2


def test_base_service_create_update_and_delete_without_commit():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        service = BaseService(BaseRepository(session, Crisis))
        crisis = service.create(_make_crisis("Enchente Teste"))

        assert service.get(crisis.id) == crisis
        assert session.in_transaction()

        updated = service.update(
            crisis.id, {"name": "Incendio Teste", "city": "Recife"}
        )

        assert updated.name == "Incendio Teste"
        assert updated.city == "Recife"

        unchanged = service.update(crisis.id, {})

        assert unchanged.name == "Incendio Teste"
        assert unchanged.city == "Recife"

        service.delete(crisis.id)

        assert service.get(crisis.id) is None
        assert session.in_transaction()
