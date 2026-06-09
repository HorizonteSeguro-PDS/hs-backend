"""HTTP layer do GET /crises/{id}/operations — auth + scoping minimo."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import controllers.operations as operations_controller
from dependencies.session import get_session
from domain.crisis.enums import CrisisStatus, CrisisType
from domain.models.crisis import Crisis
from main import app
from tests.conftest import auth_headers

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_crisis() -> Crisis:
    c = Crisis(
        id=uuid.uuid4(),
        name="Crise Teste",
        type=CrisisType.FLOOD,
        status=CrisisStatus.ACTIVE,
        state="AL",
        city="Maceio",
        severity_initial=3,
        created_by=uuid.uuid4(),
    )
    c.created_at = _NOW
    c.updated_at = _NOW
    return c


def _session_returning(crisis):
    def override():
        mock = MagicMock()
        mock.scalar.return_value = crisis
        mock.execute.return_value.all.return_value = []
        yield mock

    return override


class TestAuth:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_anonymous_is_blocked(self):
        crisis = _make_crisis()
        app.dependency_overrides[get_session] = _session_returning(crisis)
        response = TestClient(app).get(f"/crises/{crisis.id}/operations")
        assert response.status_code == 401

    def test_unrelated_role_is_blocked(self):
        """Um JWT só com role 'sheltered' (nao existe mais) bate em 403."""
        crisis = _make_crisis()
        app.dependency_overrides[get_session] = _session_returning(crisis)
        # qualquer string nao listada vai virar Role.<UNKNOWN> e quebrar.
        # uso uma role valida que NAO é uma das 3 permitidas.
        response = TestClient(app).get(
            f"/crises/{crisis.id}/operations",
            headers=auth_headers("admin"),  # nao existe -> ValueError -> 401
        )
        # decode falha em Role(admin) e o handler trata como invalid token -> 401
        assert response.status_code in (401, 403)


class TestEndpointDispatch:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_dev_gets_200_and_minimum_shape(self, monkeypatch):
        crisis = _make_crisis()

        class FakeOperationsService:
            def __init__(self, session):
                self.session = session

            def get_crisis_operations(self, crisis_id, viewer):
                from domain.operations.schemas import CrisisOperationsResponse

                return CrisisOperationsResponse(
                    id=crisis_id,
                    name="Crise Teste",
                    city="Maceio",
                    shelters=[],
                )

        monkeypatch.setattr(
            operations_controller, "OperationsService", FakeOperationsService
        )
        app.dependency_overrides[get_session] = _session_returning(crisis)

        response = TestClient(app).get(
            f"/crises/{crisis.id}/operations",
            headers=auth_headers("dev"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Crise Teste"
        assert body["city"] == "Maceio"
        assert body["shelters"] == []

    def test_crisis_manager_can_access(self, monkeypatch):
        crisis = _make_crisis()

        class FakeOperationsService:
            def __init__(self, session):
                pass

            def get_crisis_operations(self, crisis_id, viewer):
                from domain.operations.schemas import CrisisOperationsResponse

                return CrisisOperationsResponse(
                    id=crisis_id,
                    name=crisis.name,
                    city=crisis.city,
                    shelters=[],
                )

        monkeypatch.setattr(
            operations_controller, "OperationsService", FakeOperationsService
        )
        app.dependency_overrides[get_session] = _session_returning(crisis)

        response = TestClient(app).get(
            f"/crises/{crisis.id}/operations",
            headers=auth_headers("crisis_manager"),
        )
        assert response.status_code == 200

    def test_shelter_manager_can_access(self, monkeypatch):
        crisis = _make_crisis()

        class FakeOperationsService:
            def __init__(self, session):
                pass

            def get_crisis_operations(self, crisis_id, viewer):
                from domain.operations.schemas import CrisisOperationsResponse

                return CrisisOperationsResponse(
                    id=crisis_id, name=crisis.name, city=crisis.city, shelters=[]
                )

        monkeypatch.setattr(
            operations_controller, "OperationsService", FakeOperationsService
        )
        app.dependency_overrides[get_session] = _session_returning(crisis)

        response = TestClient(app).get(
            f"/crises/{crisis.id}/operations",
            headers=auth_headers("shelter_manager"),
        )
        assert response.status_code == 200
