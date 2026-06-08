import os
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from dependencies.auth import require_role

_app = FastAPI()


@_app.get("/dev-only", dependencies=[Depends(require_role("dev"))])
def _dev_only():
    return {"ok": True}


@_app.get(
    "/dev-or-crisis-manager",
    dependencies=[Depends(require_role("dev", "crisis_manager"))],
)
def _dev_or_crisis_manager():
    return {"ok": True}


def _token(*roles: str, user_id: str | None = None) -> str:
    uid = user_id or str(uuid4())
    secret = os.environ["JWT_SECRET"]
    return jwt.encode({"sub": uid, "roles": list(roles)}, secret, algorithm="HS256")


def _headers(*roles: str) -> dict:
    return {"Authorization": f"Bearer {_token(*roles)}"}


class TestJwtAuth:
    def test_no_auth_header_returns_401(self):
        response = TestClient(_app).get("/dev-only")
        assert response.status_code == 401

    def test_malformed_bearer_returns_401(self):
        response = TestClient(_app).get(
            "/dev-only", headers={"Authorization": "NotBearer garbage"}
        )
        assert response.status_code == 401

    def test_invalid_jwt_signature_returns_401(self):
        bad_token = jwt.encode(
            {"sub": str(uuid4()), "roles": ["dev"]},
            "wrong-secret",
            algorithm="HS256",
        )
        response = TestClient(_app).get(
            "/dev-only", headers={"Authorization": f"Bearer {bad_token}"}
        )
        assert response.status_code == 401

    def test_unknown_role_in_token_returns_401(self):
        # Role("foo") raises ValueError inside decode_jwt → 401
        token = jwt.encode(
            {"sub": str(uuid4()), "roles": ["foo"]},
            os.environ["JWT_SECRET"],
            algorithm="HS256",
        )
        response = TestClient(_app).get(
            "/dev-only", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    def test_missing_roles_claim_returns_401(self):
        token = jwt.encode(
            {"sub": str(uuid4())},
            os.environ["JWT_SECRET"],
            algorithm="HS256",
        )
        response = TestClient(_app).get(
            "/dev-only", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    def test_dev_allowed_on_dev_only(self):
        response = TestClient(_app).get("/dev-only", headers=_headers("dev"))
        assert response.status_code == 200

    def test_crisis_manager_rejected_from_dev_only(self):
        response = TestClient(_app).get("/dev-only", headers=_headers("crisis_manager"))
        assert response.status_code == 403

    def test_crisis_manager_allowed_on_dev_or_crisis_manager(self):
        response = TestClient(_app).get(
            "/dev-or-crisis-manager", headers=_headers("crisis_manager")
        )
        assert response.status_code == 200

    def test_shelter_manager_rejected_from_dev_or_crisis_manager(self):
        response = TestClient(_app).get(
            "/dev-or-crisis-manager", headers=_headers("shelter_manager")
        )
        assert response.status_code == 403

    def test_multi_role_user_with_one_match_is_allowed(self):
        """A user holding (crisis_manager, shelter_manager) hits an endpoint
        that requires crisis_manager — must pass (any-match semantics)."""
        response = TestClient(_app).get(
            "/dev-or-crisis-manager",
            headers=_headers("crisis_manager", "shelter_manager"),
        )
        assert response.status_code == 200
