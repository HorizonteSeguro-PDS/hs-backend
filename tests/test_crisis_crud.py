"""Integration tests for the Crisis CRUD endpoints.

Requires TEST_DATABASE_URL (or DATABASE_URL) to point to a real PostgreSQL instance.
The conftest.py runs alembic migrations once per session and truncates tables before
each test, so each test starts from a clean state.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select

from domain.models.audit_log import AuditLog
from tests.conftest import auth_headers


@pytest.fixture(autouse=True)
def _clean(clean_tables):  # noqa: PT004
    """Ensure tables are clean before every test in this module."""


CRISIS_PAYLOAD = {
    "name": "Enchente Teste",
    "type": "flood",
    "state": "SP",
    "city": "São Paulo",
    "severity_initial": 3,
}


class TestCreateCrisis:
    def test_create_as_master_returns_201(self, client, db_session):
        response = client.post(
            "/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master")
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == CRISIS_PAYLOAD["name"]
        assert body["status"] == "active"
        assert "id" in body

        audit_rows = db_session.scalars(
            select(AuditLog).where(AuditLog.action == "create")
        ).all()
        assert len(audit_rows) == 1

    def test_create_as_oversight_returns_403(self, client):
        response = client.post(
            "/crises", json=CRISIS_PAYLOAD, headers=auth_headers("oversight")
        )
        assert response.status_code == 403


class TestListCrises:
    def test_empty_list(self, client):
        response = client.get("/crises", headers=auth_headers("oversight"))
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_created_crisis(self, client):
        client.post("/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master"))
        response = client.get("/crises", headers=auth_headers("oversight"))
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_filter_by_status_active(self, client):
        client.post("/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master"))
        response = client.get(
            "/crises?status=active", headers=auth_headers("oversight")
        )
        data = response.json()
        assert all(c["status"] == "active" for c in data)

    def test_filter_by_state(self, client):
        client.post("/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master"))
        other = {**CRISIS_PAYLOAD, "state": "RJ", "city": "Rio de Janeiro"}
        client.post("/crises", json=other, headers=auth_headers("master"))

        response = client.get("/crises?state=SP", headers=auth_headers("oversight"))
        data = response.json()
        assert all(c["state"] == "SP" for c in data)


class TestGetCrisis:
    def test_get_nonexistent_returns_404(self, client):
        response = client.get(f"/crises/{uuid4()}", headers=auth_headers("master"))
        assert response.status_code == 404

    def test_get_existing_crisis(self, client):
        created = client.post(
            "/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master")
        ).json()
        response = client.get(
            f"/crises/{created['id']}", headers=auth_headers("oversight")
        )
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]


class TestUpdateCrisis:
    def test_patch_as_standard_updates_fields(self, client, db_session):
        created = client.post(
            "/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master")
        ).json()

        response = client.patch(
            f"/crises/{created['id']}",
            json={"name": "Nome Atualizado"},
            headers=auth_headers("standard"),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Nome Atualizado"

        audit_rows = db_session.scalars(
            select(AuditLog).where(AuditLog.action == "update")
        ).all()
        assert len(audit_rows) == 1


class TestCloseCrisis:
    def test_close_active_crisis(self, client, db_session):
        created = client.post(
            "/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master")
        ).json()

        response = client.post(
            f"/crises/{created['id']}/close",
            json={"close_reason": "Situação normalizada."},
            headers=auth_headers("standard"),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "closed"
        assert body["close_reason"] == "Situação normalizada."

        audit_rows = db_session.scalars(
            select(AuditLog).where(AuditLog.action == "close")
        ).all()
        assert len(audit_rows) == 1

    def test_close_already_closed_returns_409(self, client):
        created = client.post(
            "/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master")
        ).json()
        client.post(
            f"/crises/{created['id']}/close",
            json={"close_reason": "Encerrado."},
            headers=auth_headers("master"),
        )
        response = client.post(
            f"/crises/{created['id']}/close",
            json={"close_reason": "Segunda tentativa."},
            headers=auth_headers("master"),
        )
        assert response.status_code == 409


class TestReopenCrisis:
    def test_reopen_closed_crisis(self, client, db_session):
        created = client.post(
            "/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master")
        ).json()
        client.post(
            f"/crises/{created['id']}/close",
            json={"close_reason": "Encerrado."},
            headers=auth_headers("master"),
        )

        response = client.post(
            f"/crises/{created['id']}/reopen", headers=auth_headers("master")
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "active"
        assert body["closed_at"] is None

        audit_rows = db_session.scalars(
            select(AuditLog).where(AuditLog.action == "reopen")
        ).all()
        assert len(audit_rows) == 1

    def test_reopen_active_crisis_returns_409(self, client):
        created = client.post(
            "/crises", json=CRISIS_PAYLOAD, headers=auth_headers("master")
        ).json()
        response = client.post(
            f"/crises/{created['id']}/reopen", headers=auth_headers("master")
        )
        assert response.status_code == 409
