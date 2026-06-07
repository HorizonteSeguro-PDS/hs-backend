from uuid import UUID

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from dependencies.auth import CurrentUser, get_current_user, require_role
from domain.auth.enums import Role

app = FastAPI()


@app.get("/dev-only", dependencies=[Depends(require_role("dev"))])
def dev_only():
    return {"ok": True}


@app.get(
    "/dev-or-crisis-manager",
    dependencies=[Depends(require_role("dev", "crisis_manager"))],
)
def dev_or_crisis_manager():
    return {"ok": True}


def _user(*roles: Role):
    def _inner() -> CurrentUser:
        return CurrentUser(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            roles=list(roles),
        )

    return _inner


class TestRequireRole:
    def setup_method(self):
        app.dependency_overrides = {}

    def test_dev_allowed_on_dev_only(self):
        app.dependency_overrides[get_current_user] = _user(Role.DEV)
        response = TestClient(app).get("/dev-only")
        assert response.status_code == 200

    def test_crisis_manager_rejected_from_dev_only(self):
        app.dependency_overrides[get_current_user] = _user(Role.CRISIS_MANAGER)
        response = TestClient(app).get("/dev-only")
        assert response.status_code == 403

    def test_dev_allowed_on_dev_or_crisis_manager(self):
        app.dependency_overrides[get_current_user] = _user(Role.DEV)
        response = TestClient(app).get("/dev-or-crisis-manager")
        assert response.status_code == 200

    def test_crisis_manager_allowed_on_dev_or_crisis_manager(self):
        app.dependency_overrides[get_current_user] = _user(Role.CRISIS_MANAGER)
        response = TestClient(app).get("/dev-or-crisis-manager")
        assert response.status_code == 200

    def test_no_auth_header_returns_401(self):
        # No override — real get_current_user runs; no Authorization header → 401
        response = TestClient(app).get("/dev-only")
        assert response.status_code == 401

    def test_malformed_auth_header_returns_401(self):
        # HTTPBearer(auto_error=False) returns None for non-Bearer schemes → 401
        response = TestClient(app).get(
            "/dev-only", headers={"Authorization": "Invalid garbage"}
        )
        assert response.status_code == 401

    def test_user_with_no_roles_returns_403(self):
        app.dependency_overrides[get_current_user] = _user()  # empty roles
        response = TestClient(app).get("/dev-only")
        assert response.status_code == 403

    def test_multi_role_user_any_match_passes(self):
        app.dependency_overrides[get_current_user] = _user(
            Role.CRISIS_MANAGER, Role.SHELTER_MANAGER
        )
        response = TestClient(app).get("/dev-or-crisis-manager")
        assert response.status_code == 200

    def test_multi_role_user_no_match_rejected(self):
        app.dependency_overrides[get_current_user] = _user(
            Role.SHELTER_MANAGER, Role.SHELTERED
        )
        response = TestClient(app).get("/dev-only")
        assert response.status_code == 403
