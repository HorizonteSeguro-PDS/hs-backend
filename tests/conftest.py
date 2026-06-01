import os

# Must be set before any project imports — the lazy engine reads DATABASE_URL on first call.
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod")
if _test_url := os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = _test_url

import pytest
from alembic import command
from alembic.config import Config
from jose import jwt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient
from uuid import uuid4

from main import app


@pytest.fixture(scope="session")
def db_engine():
    """Session-scoped engine. Yields None when DB is not configured or unreachable."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        yield None
        return
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 10})
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
    except Exception:
        yield None
        return
    yield engine
    engine.dispose()


@pytest.fixture
def clean_tables(db_engine):
    """Truncate DB tables before each test. Only used by integration test files."""
    if db_engine is None:
        pytest.skip("DATABASE_URL not set — skipping DB integration tests")
    with db_engine.connect() as conn:
        conn.execute(text("TRUNCATE crises, audit_log RESTART IDENTITY CASCADE"))


@pytest.fixture(scope="session")
def client(db_engine):
    if db_engine is None:
        pytest.skip("DATABASE_URL not set — skipping DB integration tests")
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db_session(db_engine):
    if db_engine is None:
        pytest.skip("DATABASE_URL not set — skipping DB integration tests")
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


def make_token(role: str, user_id: str | None = None) -> str:
    uid = user_id or str(uuid4())
    payload = {"sub": uid, "role": role}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def auth_headers(role: str, user_id: str | None = None) -> dict:
    return {"Authorization": f"Bearer {make_token(role, user_id)}"}
