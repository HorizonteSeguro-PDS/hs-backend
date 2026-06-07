"""Tests for POST /auth/login — mocked authenticate, no database required."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from dependencies.session import get_session
from domain.auth.enums import Role
from domain.models.user import User
from main import app

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _user() -> User:
    u = User(
        organization_id=None,
        name="Test User",
        email="test@horizonteseguro.app",
        phone=None,
        password_hash="$bcrypt$fake",
        verified=True,
    )
    u.id = uuid.uuid4()
    u.created_at = _NOW
    u.last_login_at = None
    return u


def _session():
    def override():
        yield MagicMock()

    return override


class TestLogin:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    @patch("controllers.auth.authenticate")
    @patch(
        "controllers.auth.create_access_token", return_value=("fake.jwt.token", 86400)
    )
    def test_valid_credentials_returns_token(self, _mint, mock_auth):
        user = _user()
        mock_auth.return_value = (user, [Role.CRISIS_MANAGER])
        app.dependency_overrides[get_session] = _session()

        response = TestClient(app).post(
            "/auth/login",
            json={"email": "test@horizonteseguro.app", "password": "supersecret-1234"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "fake.jwt.token"
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 86400
        assert body["user"]["email"] == "test@horizonteseguro.app"
        assert body["user"]["roles"] == ["crisis_manager"]
        assert "password" not in body["user"]
        assert "password_hash" not in body["user"]

    @patch("controllers.auth.authenticate")
    @patch(
        "controllers.auth.create_access_token", return_value=("fake.jwt.token", 86400)
    )
    def test_multi_role_user_login_returns_all_roles(self, _mint, mock_auth):
        user = _user()
        mock_auth.return_value = (user, [Role.CRISIS_MANAGER, Role.SHELTER_MANAGER])
        app.dependency_overrides[get_session] = _session()

        response = TestClient(app).post(
            "/auth/login",
            json={"email": "test@horizonteseguro.app", "password": "supersecret-1234"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body["user"]["roles"]) == {"crisis_manager", "shelter_manager"}

    @patch("controllers.auth.authenticate", return_value=None)
    def test_invalid_credentials_returns_401(self, _auth):
        app.dependency_overrides[get_session] = _session()
        response = TestClient(app).post(
            "/auth/login",
            json={
                "email": "test@horizonteseguro.app",
                "password": "wrong-password",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid credentials"

    @patch("controllers.auth.authenticate", return_value=None)
    def test_unknown_email_returns_same_401(self, _auth):
        """Unknown email returns identical error to bad password (anti-enumeration)."""
        app.dependency_overrides[get_session] = _session()
        response = TestClient(app).post(
            "/auth/login",
            json={
                "email": "nobody@horizonteseguro.app",
                "password": "anything",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "invalid credentials"

    def test_invalid_email_format_returns_422(self):
        app.dependency_overrides[get_session] = _session()
        response = TestClient(app).post(
            "/auth/login",
            json={"email": "not-an-email", "password": "anything"},
        )
        assert response.status_code == 422

    def test_missing_fields_returns_422(self):
        app.dependency_overrides[get_session] = _session()
        response = TestClient(app).post("/auth/login", json={"email": "x@y.com"})
        assert response.status_code == 422
