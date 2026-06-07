"""Tests for POST /users — mocked session, no database required."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from dependencies.session import get_session
from domain.models.role import Role as RoleModel
from domain.models.user import User
from main import app
from tests.conftest import auth_headers

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_VALID_PAYLOAD = {
    "name": "Carlos da Silva",
    "email": "carlos@example.com",
    "password": "supersecret-1234",
    "role": "standard",
}


def _session_factory(*, integrity_error: bool = False):
    """Mock session that pretends a User got id/created_at on flush."""

    def override():
        mock = MagicMock()

        def _add(obj):
            if isinstance(obj, User):
                obj.id = uuid.uuid4()
                obj.created_at = _NOW
                obj.last_login_at = None
                if obj.verified is None:
                    obj.verified = False
            elif isinstance(obj, RoleModel):
                obj.id = uuid.uuid4()

        mock.add.side_effect = _add

        if integrity_error:

            def _flush_then_raise():
                raise IntegrityError("uq_users_email", None, None)

            # First flush (after ensure_role) succeeds; second flush
            # (after the user is added) raises. To keep this simple, just
            # raise unconditionally — controller only flushes after the user.
            mock.flush.side_effect = [None, IntegrityError("uq", None, None)]

        # ensure_role's first lookup returns None so the path that creates
        # the role row gets exercised.
        mock.scalar.return_value = None

        yield mock

    return override


class TestRegisterUser:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_unauthenticated_returns_401(self):
        app.dependency_overrides[get_session] = _session_factory()
        response = TestClient(app).post("/users", json=_VALID_PAYLOAD)
        assert response.status_code == 401

    def test_non_master_returns_403(self):
        app.dependency_overrides[get_session] = _session_factory()
        response = TestClient(app).post(
            "/users", json=_VALID_PAYLOAD, headers=auth_headers("standard")
        )
        assert response.status_code == 403

    @patch("controllers.user.hash_password", return_value="$bcrypt$fake")
    def test_master_can_register(self, _hash):
        app.dependency_overrides[get_session] = _session_factory()
        response = TestClient(app).post(
            "/users", json=_VALID_PAYLOAD, headers=auth_headers("master")
        )
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == _VALID_PAYLOAD["email"]
        assert body["name"] == _VALID_PAYLOAD["name"]
        assert body["role"] == "standard"
        assert body["verified"] is False
        assert "id" in body
        # password must not leak
        assert "password" not in body
        assert "password_hash" not in body

    @patch("controllers.user.hash_password", return_value="$bcrypt$fake")
    def test_duplicate_email_returns_409(self, _hash):
        app.dependency_overrides[get_session] = _session_factory(integrity_error=True)
        response = TestClient(app).post(
            "/users", json=_VALID_PAYLOAD, headers=auth_headers("master")
        )
        assert response.status_code == 409

    def test_invalid_email_returns_422(self):
        app.dependency_overrides[get_session] = _session_factory()
        bad = dict(_VALID_PAYLOAD, email="not-an-email")
        response = TestClient(app).post(
            "/users", json=bad, headers=auth_headers("master")
        )
        assert response.status_code == 422

    def test_short_password_returns_422(self):
        app.dependency_overrides[get_session] = _session_factory()
        bad = dict(_VALID_PAYLOAD, password="short")
        response = TestClient(app).post(
            "/users", json=bad, headers=auth_headers("master")
        )
        assert response.status_code == 422

    def test_invalid_role_returns_422(self):
        app.dependency_overrides[get_session] = _session_factory()
        bad = dict(_VALID_PAYLOAD, role="superuser")
        response = TestClient(app).post(
            "/users", json=bad, headers=auth_headers("master")
        )
        assert response.status_code == 422
