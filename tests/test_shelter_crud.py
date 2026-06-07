"""CRUD tests for shelter endpoints - fully mocked, no database required."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from dependencies.session import get_session
from domain.models.shelter import Shelter
from domain.schemas.enums import ShelterStatus, ShelterType
from main import app
from tests.conftest import auth_headers

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _shelter_payload(**kwargs) -> dict:
    return {
        "name": kwargs.get("name", "Abrigo Central"),
        "address": kwargs.get("address", "Rua Principal, 100"),
        "latitude": kwargs.get("latitude", -23.55),
        "longitude": kwargs.get("longitude", -46.63),
        "capacity": kwargs.get("capacity", 100),
        "occupation": kwargs.get("occupation", 25),
        "shelter_type": kwargs.get("shelter_type", ShelterType.INSTITUTIONAL.value),
    }


def _make_shelter(**kwargs) -> Shelter:
    shelter = Shelter(
        id=kwargs.get("id", uuid.uuid4()),
        organization_id=kwargs.get("organization_id"),
        responsible_user_id=kwargs.get("responsible_user_id", uuid.uuid4()),
        created_by=kwargs.get("created_by", uuid.uuid4()),
        verified_by=kwargs.get("verified_by"),
        name=kwargs.get("name", "Abrigo Central"),
        address=kwargs.get("address", "Rua Principal, 100"),
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


def _session_returning(shelters: list[Shelter], total: int | None = None):
    def override():
        mock = MagicMock()
        mock.scalar.return_value = len(shelters) if total is None else total
        mock.scalars.return_value = shelters
        yield mock

    return override


def _session_get(shelter: Shelter | None):
    def override():
        mock = MagicMock()
        mock.get.return_value = shelter
        yield mock

    return override


def _session_for_create():
    def override():
        mock = MagicMock()

        def _add(obj):
            if isinstance(obj, Shelter):
                obj.id = uuid.uuid4()
                obj.created_at = _NOW
                obj.updated_at = _NOW

        mock.add.side_effect = _add
        yield mock

    return override


class TestListShelters:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_empty_list(self):
        app.dependency_overrides[get_session] = _session_returning([])
        response = TestClient(app).get("/shelters", headers=auth_headers("sheltered"))

        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 10,
            "pages": 0,
        }

    def test_returns_paginated_shelters(self):
        shelters = [
            _make_shelter(name="Abrigo 1"),
            _make_shelter(name="Abrigo 2", shelter_type=ShelterType.IMPROVISED_PUBLIC),
        ]
        app.dependency_overrides[get_session] = _session_returning(shelters)
        response = TestClient(app).get(
            "/shelters?page=1&size=10", headers=auth_headers("dev")
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        assert body["items"][0]["name"] == "Abrigo 1"
        assert "created_by" not in body["items"][0]
        assert "crisis_id" not in body["items"][0]


class TestGetShelter:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_get_existing_shelter(self):
        shelter = _make_shelter()
        app.dependency_overrides[get_session] = _session_get(shelter)
        response = TestClient(app).get(
            f"/shelters/{shelter.id}", headers=auth_headers("crisis_manager")
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(shelter.id)
        assert body["name"] == shelter.name
        assert body["created_by"] == str(shelter.created_by)

    def test_get_nonexistent_shelter_returns_404(self):
        app.dependency_overrides[get_session] = _session_get(None)
        response = TestClient(app).get(
            f"/shelters/{uuid.uuid4()}", headers=auth_headers("dev")
        )

        assert response.status_code == 404


class TestCreateShelter:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_create_as_shelter_manager_uses_authenticated_user_as_created_by(self):
        user_id = uuid.uuid4()
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/shelters",
            json=_shelter_payload(),
            headers=auth_headers("shelter_manager", user_id=str(user_id)),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Abrigo Central"
        assert body["created_by"] == str(user_id)
        assert body["responsible_user_id"] == str(user_id)
        assert body["organization_id"] is None
        assert body["verified"] is False
        assert body["verified_by"] is None
        assert body["status"] == "preparing"

    def test_create_does_not_require_administrative_fields_in_payload(self):
        payload = _shelter_payload()
        assert "created_by" not in payload
        assert "responsible_user_id" not in payload
        assert "verified_by" not in payload
        assert "verified" not in payload
        assert "status" not in payload
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/shelters", json=payload, headers=auth_headers("dev")
        )

        assert response.status_code == 201

    def test_create_rejects_administrative_fields(self):
        payload = {
            **_shelter_payload(),
            "created_by": str(uuid.uuid4()),
            "responsible_user_id": str(uuid.uuid4()),
            "verified_by": str(uuid.uuid4()),
            "status": "active",
            "verified": True,
            "crisis_id": str(uuid.uuid4()),
        }
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/shelters", json=payload, headers=auth_headers("dev")
        )

        assert response.status_code == 422

    def test_create_as_sheltered_returns_403(self):
        app.dependency_overrides[get_session] = _session_for_create()
        response = TestClient(app).post(
            "/shelters", json=_shelter_payload(), headers=auth_headers("sheltered")
        )

        assert response.status_code == 403


class TestUpdateShelter:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_patch_as_shelter_manager_updates_fields(self):
        shelter = _make_shelter(name="Abrigo Antigo", occupation=10)
        app.dependency_overrides[get_session] = _session_get(shelter)
        response = TestClient(app).patch(
            f"/shelters/{shelter.id}",
            json={"name": "Abrigo Novo", "occupation": 40},
            headers=auth_headers("shelter_manager"),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "Abrigo Novo"
        assert body["occupation"] == 40

    def test_patch_nonexistent_returns_404(self):
        app.dependency_overrides[get_session] = _session_get(None)
        response = TestClient(app).patch(
            f"/shelters/{uuid.uuid4()}",
            json={"name": "Abrigo Novo"},
            headers=auth_headers("dev"),
        )

        assert response.status_code == 404

    def test_patch_rejects_administrative_fields(self):
        shelter = _make_shelter(verified=False, status=ShelterStatus.PREPARING)
        app.dependency_overrides[get_session] = _session_get(shelter)
        response = TestClient(app).patch(
            f"/shelters/{shelter.id}",
            json={"verified": True, "status": "active", "crisis_id": str(uuid.uuid4())},
            headers=auth_headers("shelter_manager"),
        )

        assert response.status_code == 422
        assert shelter.verified is False
        assert shelter.status == ShelterStatus.PREPARING


class TestDeleteShelter:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_delete_as_dev_returns_204(self):
        shelter = _make_shelter()
        app.dependency_overrides[get_session] = _session_get(shelter)
        response = TestClient(app).delete(
            f"/shelters/{shelter.id}", headers=auth_headers("dev")
        )

        assert response.status_code == 204
        assert response.content == b""

    def test_delete_as_crisis_manager_returns_403(self):
        shelter = _make_shelter()
        app.dependency_overrides[get_session] = _session_get(shelter)
        response = TestClient(app).delete(
            f"/shelters/{shelter.id}", headers=auth_headers("crisis_manager")
        )

        assert response.status_code == 403

    def test_delete_nonexistent_returns_404(self):
        app.dependency_overrides[get_session] = _session_get(None)
        response = TestClient(app).delete(
            f"/shelters/{uuid.uuid4()}", headers=auth_headers("shelter_manager")
        )

        assert response.status_code == 404
