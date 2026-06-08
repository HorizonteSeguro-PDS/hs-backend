import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from main import app

# Configuração mínima
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")


@pytest.fixture(scope="session")
def client():
    """Cliente HTTP para testes - SEM BANCO"""
    with TestClient(app) as c:
        yield c


def make_token(
    *roles: str,
    user_id: str | None = None,
    organization_id: str | UUID | None = None,
) -> str:
    uid = user_id or str(uuid4())
    payload = {"sub": uid, "roles": list(roles)}
    if organization_id is not None:
        payload["organization_id"] = str(organization_id)
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def auth_headers(
    *roles: str,
    user_id: str | None = None,
    organization_id: str | UUID | None = None,
) -> dict:
    return {
        "Authorization": (
            f"Bearer {make_token(*roles, user_id=user_id, organization_id=organization_id)}"
        )
    }
