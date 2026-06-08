"""Tests for POST /users — mocked session, no database required."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from dependencies.session import get_session
from domain.models.user import User
from domain.models.user_role import UserRole
from main import app
from tests.conftest import auth_headers

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)

_VALID_PAYLOAD = {
    "name": "Carlos da Silva",
    "email": "carlos@horizonteseguro.app",
    "password": "supersecret-1234",
    "roles": ["shelter_manager"],
}


def _session_factory(*, integrity_error: bool = False):
    """Mock session that stamps id/created_at on User on flush()."""

    def override():
        mock = MagicMock()

        def _add(obj):
            if isinstance(obj, User):
                obj.id = uuid.uuid4()
                obj.created_at = _NOW
                obj.last_login_at = None
                if obj.verified is None:
                    obj.verified = False
            elif isinstance(obj, UserRole):
                pass  # nothing to fill

        mock.add.side_effect = _add

        if integrity_error:
            mock.flush.side_effect = IntegrityError("uq_users_email", None, None)

        # ensure no existing UserRole rows are found, so grant_role inserts
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

    def test_shelter_manager_cannot_create_anyone(self):
        """shelter_manager is now the bottom of the matrix — creates nothing."""
        app.dependency_overrides[get_session] = _session_factory()
        response = TestClient(app).post(
            "/users",
            json=_VALID_PAYLOAD,
            headers=auth_headers("shelter_manager"),
        )
        assert response.status_code == 403

    def test_crisis_manager_can_create_shelter_manager(self):
        app.dependency_overrides[get_session] = _session_factory()
        with patch("controllers.user.hash_password", return_value="$bcrypt$fake"):
            response = TestClient(app).post(
                "/users", json=_VALID_PAYLOAD, headers=auth_headers("crisis_manager")
            )
        assert response.status_code == 201

    def test_crisis_manager_cannot_create_dev(self):
        app.dependency_overrides[get_session] = _session_factory()
        payload = dict(_VALID_PAYLOAD, roles=["dev"])
        response = TestClient(app).post(
            "/users", json=payload, headers=auth_headers("crisis_manager")
        )
        assert response.status_code == 403

    def test_crisis_manager_cannot_create_another_crisis_manager(self):
        """crisis_manager can ONLY create shelter_manager — not another peer."""
        app.dependency_overrides[get_session] = _session_factory()
        payload = dict(_VALID_PAYLOAD, roles=["crisis_manager"])
        response = TestClient(app).post(
            "/users", json=payload, headers=auth_headers("crisis_manager")
        )
        assert response.status_code == 403

    def test_dev_can_create_any_role(self):
        app.dependency_overrides[get_session] = _session_factory()
        with patch("controllers.user.hash_password", return_value="$bcrypt$fake"):
            for role in ("dev", "crisis_manager", "shelter_manager"):
                response = TestClient(app).post(
                    "/users",
                    json=dict(
                        _VALID_PAYLOAD,
                        email=f"{role}@horizonteseguro.app",
                        roles=[role],
                    ),
                    headers=auth_headers("dev"),
                )
                assert response.status_code == 201, (role, response.json())

    def test_dev_can_create_multi_role_user(self):
        app.dependency_overrides[get_session] = _session_factory()
        payload = dict(
            _VALID_PAYLOAD,
            email="multi@horizonteseguro.app",
            roles=["crisis_manager", "shelter_manager"],
        )
        with patch("controllers.user.hash_password", return_value="$bcrypt$fake"):
            response = TestClient(app).post(
                "/users", json=payload, headers=auth_headers("dev")
            )
        assert response.status_code == 201
        assert set(response.json()["roles"]) == {"crisis_manager", "shelter_manager"}

    def test_crisis_manager_cannot_create_mixed_authorized_and_unauthorized(self):
        """If the target role list contains ANY role the actor can't create,
        the whole request fails (no partial creation)."""
        app.dependency_overrides[get_session] = _session_factory()
        payload = dict(_VALID_PAYLOAD, roles=["shelter_manager", "dev"])
        response = TestClient(app).post(
            "/users", json=payload, headers=auth_headers("crisis_manager")
        )
        assert response.status_code == 403

    def test_password_never_in_response(self):
        app.dependency_overrides[get_session] = _session_factory()
        with patch("controllers.user.hash_password", return_value="$bcrypt$fake"):
            response = TestClient(app).post(
                "/users", json=_VALID_PAYLOAD, headers=auth_headers("dev")
            )
        assert response.status_code == 201
        body = response.json()
        assert "password" not in body
        assert "password_hash" not in body

    def test_duplicate_email_returns_409(self):
        app.dependency_overrides[get_session] = _session_factory(integrity_error=True)
        with patch("controllers.user.hash_password", return_value="$bcrypt$fake"):
            response = TestClient(app).post(
                "/users", json=_VALID_PAYLOAD, headers=auth_headers("dev")
            )
        assert response.status_code == 409

    def test_invalid_email_returns_422(self):
        app.dependency_overrides[get_session] = _session_factory()
        bad = dict(_VALID_PAYLOAD, email="not-an-email")
        response = TestClient(app).post("/users", json=bad, headers=auth_headers("dev"))
        assert response.status_code == 422

    def test_short_password_returns_422(self):
        app.dependency_overrides[get_session] = _session_factory()
        bad = dict(_VALID_PAYLOAD, password="short")
        response = TestClient(app).post("/users", json=bad, headers=auth_headers("dev"))
        assert response.status_code == 422

    def test_invalid_role_returns_422(self):
        """sheltered no longer exists — must be rejected at the Pydantic layer."""
        app.dependency_overrides[get_session] = _session_factory()
        bad = dict(_VALID_PAYLOAD, roles=["sheltered"])
        response = TestClient(app).post("/users", json=bad, headers=auth_headers("dev"))
        assert response.status_code == 422

    def test_unknown_role_returns_422(self):
        app.dependency_overrides[get_session] = _session_factory()
        bad = dict(_VALID_PAYLOAD, roles=["superuser"])
        response = TestClient(app).post("/users", json=bad, headers=auth_headers("dev"))
        assert response.status_code == 422

    def test_empty_roles_returns_422(self):
        app.dependency_overrides[get_session] = _session_factory()
        bad = dict(_VALID_PAYLOAD, roles=[])
        response = TestClient(app).post("/users", json=bad, headers=auth_headers("dev"))
        assert response.status_code == 422
