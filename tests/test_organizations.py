import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from dependencies.session import get_session
from domain.models.organization import Organization
from domain.schemas.enums import OrganizationType
from main import app

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


def _organization(name: str) -> Organization:
    organization = Organization(
        name=name,
        cnpj=None,
        type=OrganizationType.SHELTER_OPERATOR,
        contact_email=None,
    )
    organization.id = uuid.uuid4()
    organization.created_at = _NOW
    return organization


def _session_factory(rows):
    def override():
        class Session:
            def scalars(self, _stmt):
                return _ScalarResult(rows)

        yield Session()

    return override


class TestOrganizationSearch:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_search_organizations_is_public_and_returns_safe_fields(self):
        app.dependency_overrides[get_session] = _session_factory(
            [_organization("Defesa Civil")]
        )

        response = TestClient(app).get("/organizations/search?q=defesa")

        assert response.status_code == 200
        body = response.json()
        assert body == [{"id": body[0]["id"], "name": "Defesa Civil"}]
        assert set(body[0]) == {"id", "name"}
