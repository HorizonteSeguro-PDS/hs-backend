"""HTTP layer do GET /crises/{id}/operations.

Endpoint é PUBLICO (não exige token). Front controla visibilidade de
botões de gerenciamento por role. Aqui só validamos dispatch + commit-not-
needed (read endpoint).
"""

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


class TestPublicAccess:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_anonymous_access_is_allowed(self, monkeypatch):
        """Endpoint é publico — sem token, devolve 200."""
        crisis = _make_crisis()

        class FakeOperationsService:
            def __init__(self, session):
                self.session = session

            def get_crisis_operations(self, crisis_id, viewer=None):
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

        response = TestClient(app).get(f"/crises/{crisis.id}/operations")
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Crise Teste"
        assert body["city"] == "Maceio"
        assert body["shelters"] == []

    def test_authenticated_access_still_works(self, monkeypatch):
        """Token aceito (mesmo nao sendo obrigatorio) — não muda o response."""
        crisis = _make_crisis()

        class FakeOperationsService:
            def __init__(self, session):
                self.session = session

            def get_crisis_operations(self, crisis_id, viewer=None):
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
            headers=auth_headers("dev"),
        )
        assert response.status_code == 200
