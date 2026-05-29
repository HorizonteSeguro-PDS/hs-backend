from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dependencies.auth import CurrentUser, get_current_user, require_role

app = FastAPI()


@app.get("/master-only", dependencies=[Depends(require_role("master"))])
def master_only():
    return {"ok": True}


@app.get("/master-or-padrao", dependencies=[Depends(require_role("master", "padrao"))])
def master_or_padrao():
    return {"ok": True}


def _user(role: str):
    def _inner() -> CurrentUser:
        return CurrentUser(id=UUID("00000000-0000-0000-0000-000000000001"), role=role)

    return _inner


class TestRequireRole:
    def setup_method(self):
        app.dependency_overrides = {}

    def test_master_allowed_on_master_only(self):
        app.dependency_overrides[get_current_user] = _user("master")
        response = TestClient(app).get("/master-only")
        assert response.status_code == 200

    def test_padrao_rejected_from_master_only(self):
        app.dependency_overrides[get_current_user] = _user("padrao")
        response = TestClient(app).get("/master-only")
        assert response.status_code == 403

    def test_master_allowed_on_master_or_padrao(self):
        app.dependency_overrides[get_current_user] = _user("master")
        response = TestClient(app).get("/master-or-padrao")
        assert response.status_code == 200

    def test_padrao_allowed_on_master_or_padrao(self):
        app.dependency_overrides[get_current_user] = _user("padrao")
        response = TestClient(app).get("/master-or-padrao")
        assert response.status_code == 200

    def test_no_auth_header_returns_401(self):
        # No override — real get_current_user runs; no Authorization header → 401
        response = TestClient(app).get("/master-only")
        assert response.status_code == 401

    def test_malformed_auth_header_returns_401(self):
        # HTTPBearer(auto_error=False) returns None for non-Bearer schemes → 401
        response = TestClient(app).get(
            "/master-only", headers={"Authorization": "Invalid garbage"}
        )
        assert response.status_code == 401

    def test_unknown_role_returns_403(self):
        app.dependency_overrides[get_current_user] = _user("desconhecido")
        response = TestClient(app).get("/master-only")
        assert response.status_code == 403
