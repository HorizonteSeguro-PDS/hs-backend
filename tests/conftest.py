import os
import pytest
from jose import jwt
from uuid import uuid4
from fastapi.testclient import TestClient

from main import app

# Configuração mínima
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")

@pytest.fixture(scope="session")
def client():
    """Cliente HTTP para testes - SEM BANCO"""
    with TestClient(app) as c:
        yield c

def make_token(role: str, user_id: str | None = None) -> str:
    uid = user_id or str(uuid4())
    payload = {"sub": uid, "role": role}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")

def auth_headers(role: str, user_id: str | None = None) -> dict:
    return {"Authorization": f"Bearer {make_token(role, user_id)}"}