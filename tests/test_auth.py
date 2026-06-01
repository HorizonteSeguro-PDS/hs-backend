import os
from uuid import uuid4

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from dependencies.auth import require_role

_app = FastAPI()


@_app.get("/master-only", dependencies=[Depends(require_role("master"))])
def _master_only():
    return {"ok": True}


@_app.get(
    "/master-or-standard", dependencies=[Depends(require_role("master", "standard"))]
)
def _master_or_standard():
    return {"ok": True}


def _token(role: str, user_id: str | None = None) -> str:
    uid = user_id or str(uuid4())
    secret = os.environ["JWT_SECRET"]
    return jwt.encode({"sub": uid, "role": role}, secret, algorithm="HS256")


def _headers(role: str) -> dict:
    return {"Authorization": f"Bearer {_token(role)}"}


class TestJwtAuth:
    def test_no_auth_header_returns_401(self):
        response = TestClient(_app).get("/master-only")
        assert response.status_code == 401

    def test_malformed_bearer_returns_401(self):
        response = TestClient(_app).get(
            "/master-only", headers={"Authorization": "NotBearer garbage"}
        )
        assert response.status_code == 401

    def test_invalid_jwt_signature_returns_401(self):
        bad_token = jwt.encode(
            {"sub": str(uuid4()), "role": "master"}, "wrong-secret", algorithm="HS256"
        )
        response = TestClient(_app).get(
            "/master-only", headers={"Authorization": f"Bearer {bad_token}"}
        )
        assert response.status_code == 401

    def test_unknown_role_in_token_returns_401(self):
        # Role("foo") raises ValueError inside decode_jwt → 401
        token = jwt.encode(
            {"sub": str(uuid4()), "role": "foo"},
            os.environ["JWT_SECRET"],
            algorithm="HS256",
        )
        response = TestClient(_app).get(
            "/master-only", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    def test_master_allowed_on_master_only(self):
        response = TestClient(_app).get("/master-only", headers=_headers("master"))
        assert response.status_code == 200

    def test_standard_rejected_from_master_only(self):
        response = TestClient(_app).get("/master-only", headers=_headers("standard"))
        assert response.status_code == 403

    def test_standard_allowed_on_master_or_standard(self):
        response = TestClient(_app).get(
            "/master-or-standard", headers=_headers("standard")
        )
        assert response.status_code == 200

    def test_oversight_rejected_from_master_or_standard(self):
        response = TestClient(_app).get(
            "/master-or-standard", headers=_headers("oversight")
        )
        assert response.status_code == 403
