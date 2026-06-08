"""CRUD tests for crisis endpoints — fully mocked, no database required."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import controllers.crisis as crisis_controller
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
    c.shelters_count = kwargs.get("shelters_count", 0)
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
                obj.shelters_count = 0
                if obj.status is None:
                    obj.status = CrisisStatus.ACTIVE

        mock.add.side_effect = _add
        yield mock

    return override


def _session_returning(crises: list, total: int | None = None):
    """Session mock for CrisisRepository.list_paginated()."""

    def override():
        mock = MagicMock()
        mock.scalar.return_value = len(crises) if total is None else total
        mock.execute.return_value.all.return_value = [
            (crisis, getattr(crisis, "shelters_count", 0)) for crisis in crises
        ]
        yield mock

    return override


def _session_get(crisis):
    """Session mock for CrisisRepository.get_with_shelters()."""

    def override():
        mock = MagicMock()
        mock.get.return_value = crisis
        mock.scalar.return_value = crisis
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

    def test_create_accepts_modal_payload_aliases(self):
        organization_id = uuid.uuid4()
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/crises",
            json={
                "name": "Sao Paulo Crisis",
                "severity": "ALTA",
                "state": "Sao Paulo",
                "city": "Sao Paulo",
                "start_date": "2024-01-01",
                "status": "ATIVA",
                "type": "FLOOD",
            },
            headers=auth_headers("dev", organization_id=organization_id),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["organization_id"] == str(organization_id)
        assert body["severity_initial"] == 4
        assert body["state"] == "SP"
        assert body["start_date"] == "2024-01-01"
        assert body["status"] == "active"
        assert body["type"] == "flood"

    def test_create_rejects_organization_id_in_body(self):
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/crises",
            json={**_FLOOD_PAYLOAD, "organization_id": str(uuid.uuid4())},
            headers=auth_headers("dev"),
        )

        assert response.status_code == 422

    def test_create_as_shelter_manager_returns_403(self):
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/crises", json=_FLOOD_PAYLOAD, headers=auth_headers("shelter_manager")
        )
        assert response.status_code == 403


class TestListCrises:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_list_is_public_no_token_needed(self):
        """GET /crises is public — visualização não exige autenticação."""
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get("/crises")
        assert response.status_code == 200

    def test_get_one_is_public_no_token_needed(self):
        crisis = _make_crisis()
        app.dependency_overrides[get_session] = _session_get(crisis)
        response = TestClient(app).get(f"/crises/{crisis.id}")
        assert response.status_code == 200

    def test_empty_list(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises", headers=auth_headers("shelter_manager")
        )
        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 10,
            "pages": 0,
        }

    def test_returns_crises(self):
        crises = [
            _make_crisis(),
            _make_crisis(name="Incêndio BA", type=CrisisType.FIRE),
        ]
        app.dependency_overrides[get_session] = _session_returning(crises)
        response = TestClient(app).get("/crises", headers=auth_headers("dev"))
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 2
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["size"] == 10
        assert body["pages"] == 1
        assert body["items"][0]["shelters_count"] == 0
        assert "created_by" not in body["items"][0]
        assert "close_reason" not in body["items"][0]

    def test_uses_requested_page_and_size(self):
        crises = [_make_crisis(name="Incêndio BA", type=CrisisType.FIRE)]
        app.dependency_overrides[get_session] = _session_returning(crises, total=2)
        response = TestClient(app).get(
            "/crises?page=2&size=1", headers=auth_headers("dev")
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["total"] == 2
        assert body["page"] == 2
        assert body["size"] == 1
        assert body["pages"] == 2

    def test_filter_by_status_param_accepted(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises?status=active", headers=auth_headers("crisis_manager")
        )
        assert response.status_code == 200

    def test_filter_by_state_param_accepted(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises?state=SP", headers=auth_headers("shelter_manager")
        )
        assert response.status_code == 200

    def test_filter_by_type_param_is_forwarded_to_service(self, monkeypatch):
        captured = {}

        class FakeCrisisService:
            def __init__(self, repository):
                self.repository = repository

            def list_crises(
                self,
                params,
                *,
                status=None,
                state=None,
                type_=None,
            ):
                captured["type_"] = type_
                return {
                    "items": [],
                    "total": 0,
                    "page": params.page,
                    "size": params.size,
                    "pages": 0,
                }

        monkeypatch.setattr(crisis_controller, "CrisisService", FakeCrisisService)
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises?type=flood", headers=auth_headers("shelter_manager")
        )
        assert response.status_code == 200
        assert captured["type_"] == CrisisType.FLOOD

    def test_page_must_start_at_one(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises?page=0", headers=auth_headers("shelter_manager")
        )
        assert response.status_code == 422

    def test_size_has_max_limit(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises?size=101", headers=auth_headers("shelter_manager")
        )
        assert response.status_code == 422

    def test_size_max_limit_is_accepted(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get(
            "/crises?size=100", headers=auth_headers("shelter_manager")
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
            f"/crises/{crisis.id}", headers=auth_headers("shelter_manager")
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
