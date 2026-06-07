"""CRUD tests for crisis endpoints — fully mocked, no database required."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from dependencies.session import get_session
from domain.crisis.enums import CrisisStatus, CrisisType
from domain.models.crisis import Crisis
from main import app
from tests.conftest import auth_headers

_FLOOD_PAYLOAD = {
    "name": "Enchente Teste",
    "type": "flood",
    "state": "SP",
    "city": "São Paulo",
    "severity_initial": 3,
}

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_crisis(**kwargs) -> Crisis:
    c = Crisis(
        name=kwargs.get("name", "Enchente Teste"),
        type=kwargs.get("type", CrisisType.FLOOD),
        status=kwargs.get("status", CrisisStatus.ACTIVE),
        state=kwargs.get("state", "SP"),
        city=kwargs.get("city", "São Paulo"),
        severity_initial=kwargs.get("severity_initial", 3),
        severity_calculated=kwargs.get("severity_calculated", None),
        created_by=kwargs.get("created_by", uuid.uuid4()),
        close_reason=kwargs.get("close_reason", None),
    )
    c.id = kwargs.get("id", uuid.uuid4())
    c.created_at = kwargs.get("created_at", _NOW)
    c.updated_at = kwargs.get("updated_at", _NOW)
    return c


def _session_for_create():
    """Session mock that assigns id/timestamps when add() is called."""

    def override():
        mock = MagicMock()

        def _add(obj):
            if isinstance(obj, Crisis):
                obj.id = uuid.uuid4()
                obj.created_at = _NOW
                obj.updated_at = _NOW
                if obj.status is None:
                    obj.status = CrisisStatus.ACTIVE

        mock.add.side_effect = _add
        yield mock

    return override


def _session_returning(crises: list):
    """Session mock whose scalars() returns an iterable (controller uses list())."""

    def override():
        mock = MagicMock()
        mock.scalars.return_value = crises
        yield mock

    return override


def _session_get(crisis):
    """Session mock whose get() returns the given object (or None)."""

    def override():
        mock = MagicMock()
        mock.get.return_value = crisis
        yield mock

    return override


class TestCreateCrisis:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_create_as_dev_returns_201(self):
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/crises", json=_FLOOD_PAYLOAD, headers=auth_headers("dev")
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == _FLOOD_PAYLOAD["name"]
        assert body["status"] == "active"
        assert body["type"] == "flood"
        assert "id" in body

    def test_create_as_sheltered_returns_403(self):
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/crises", json=_FLOOD_PAYLOAD, headers=auth_headers("sheltered")
        )
        assert response.status_code == 403


class TestListCrises:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_empty_list(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get("/crises", headers=auth_headers("sheltered"))
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_crises(self):
        crises = [
            _make_crisis(),
            _make_crisis(name="Incêndio BA", type=CrisisType.FIRE),
        ]
        app.dependency_overrides[get_session] = _session_returning(crises)
        response = TestClient(app).get("/crises", headers=auth_headers("dev"))
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_filter_by_status_param_accepted(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises?status=active", headers=auth_headers("crisis_manager")
        )
        assert response.status_code == 200

    def test_filter_by_state_param_accepted(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises?state=SP", headers=auth_headers("sheltered")
        )
        assert response.status_code == 200


class TestGetCrisis:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_get_nonexistent_returns_404(self):
        app.dependency_overrides[get_session] = _session_get(None)
        response = TestClient(app).get(
            f"/crises/{uuid.uuid4()}", headers=auth_headers("dev")
        )
        assert response.status_code == 404

    def test_get_existing_crisis(self):
        crisis = _make_crisis()
        app.dependency_overrides[get_session] = _session_get(crisis)
        response = TestClient(app).get(
            f"/crises/{crisis.id}", headers=auth_headers("sheltered")
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(crisis.id)
        assert response.json()["name"] == crisis.name


class TestUpdateCrisis:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_patch_as_crisis_manager_updates_fields(self):
        crisis = _make_crisis(name="Original")
        app.dependency_overrides[get_session] = _session_get(crisis)
        response = TestClient(app).patch(
            f"/crises/{crisis.id}",
            json={"name": "Atualizado"},
            headers=auth_headers("crisis_manager"),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Atualizado"

    def test_patch_nonexistent_returns_404(self):
        app.dependency_overrides[get_session] = _session_get(None)
        response = TestClient(app).patch(
            f"/crises/{uuid.uuid4()}",
            json={"name": "X"},
            headers=auth_headers("dev"),
        )
        assert response.status_code == 404


class TestCloseCrisis:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_close_active_crisis(self):
        crisis = _make_crisis(status=CrisisStatus.ACTIVE)
        app.dependency_overrides[get_session] = _session_get(crisis)
        response = TestClient(app).post(
            f"/crises/{crisis.id}/close",
            json={"close_reason": "Situação normalizada."},
            headers=auth_headers("crisis_manager"),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "closed"

    def test_close_already_closed_returns_409(self):
        crisis = _make_crisis(status=CrisisStatus.CLOSED)
        app.dependency_overrides[get_session] = _session_get(crisis)
        response = TestClient(app).post(
            f"/crises/{crisis.id}/close",
            json={"close_reason": "Segunda tentativa."},
            headers=auth_headers("dev"),
        )
        assert response.status_code == 409


class TestReopenCrisis:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_reopen_closed_crisis(self):
        crisis = _make_crisis(status=CrisisStatus.CLOSED)
        app.dependency_overrides[get_session] = _session_get(crisis)
        response = TestClient(app).post(
            f"/crises/{crisis.id}/reopen",
            headers=auth_headers("dev"),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_reopen_active_crisis_returns_409(self):
        crisis = _make_crisis(status=CrisisStatus.ACTIVE)
        app.dependency_overrides[get_session] = _session_get(crisis)
        response = TestClient(app).post(
            f"/crises/{crisis.id}/reopen",
            headers=auth_headers("dev"),
        )
        assert response.status_code == 409
