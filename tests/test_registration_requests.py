import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from dependencies.session import get_session
from domain.auth.enums import Role
from domain.models.organization import Organization
from domain.models.registration_request import RegistrationRequest
from domain.models.user import User
from domain.models.user_role import UserRole
from domain.schemas.enums import OrganizationType
from main import app
from tests.conftest import auth_headers

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(
        self,
        *,
        organizations=None,
        requests=None,
        scalar_results=None,
        list_rows=None,
    ):
        self.organizations = organizations or {}
        self.requests = requests or {}
        self.scalar_results = list(scalar_results or [])
        self.list_rows = list_rows or []
        self.added = []
        self.committed = False
        self.rolled_back = False

    def get(self, model, id_):
        if model is Organization:
            return self.organizations.get(id_)
        if model is RegistrationRequest:
            return self.requests.get(id_)
        return None

    def scalar(self, _stmt):
        if self.scalar_results:
            return self.scalar_results.pop(0)
        return None

    def scalars(self, _stmt):
        return _ScalarResult(self.list_rows)

    def add(self, obj):
        self.added.append(obj)
        if isinstance(obj, RegistrationRequest):
            obj.id = uuid.uuid4()
            obj.created_at = _NOW
            obj.reviewed_at = None
            obj.reviewed_by = None
            obj.user_id = None
            obj.created_organization_id = None
        elif isinstance(obj, Organization):
            obj.id = uuid.uuid4()
            obj.created_at = _NOW
        elif isinstance(obj, User):
            obj.id = uuid.uuid4()
            obj.created_at = _NOW
            obj.last_login_at = None
        elif isinstance(obj, UserRole):
            pass

    def flush(self):
        pass

    def commit(self):
        self.committed = True

    def refresh(self, _obj):
        pass

    def rollback(self):
        self.rolled_back = True


def _override(session):
    def dependency():
        yield session

    return dependency


def _organization() -> Organization:
    organization = Organization(
        name="Defesa Civil",
        cnpj=None,
        type=OrganizationType.SHELTER_OPERATOR,
        contact_email=None,
    )
    organization.id = uuid.uuid4()
    organization.created_at = _NOW
    return organization


def _user(email: str = "used@horizonteseguro.app") -> User:
    user = User(
        organization_id=None,
        name="Used User",
        email=email,
        phone=None,
        password_hash="$bcrypt$fake",
        verified=True,
    )
    user.id = uuid.uuid4()
    user.created_at = _NOW
    user.last_login_at = None
    return user


def _registration_request(
    *,
    request_type: str = "existing_organization",
    organization_id: uuid.UUID | None = None,
    status: str = "pending",
) -> RegistrationRequest:
    request = RegistrationRequest(
        status=status,
        request_type=request_type,
        name="Carlos da Silva",
        email="carlos@horizonteseguro.app",
        phone="82999999999",
        password_hash="$bcrypt$fake",
        roles=[Role.SHELTER_MANAGER.value],
        organization_id=organization_id,
        new_organization_name=(
            "Nova Defesa Civil" if request_type == "new_organization" else None
        ),
        new_organization_cnpj=None,
        new_organization_type=(
            OrganizationType.SHELTER_OPERATOR.value
            if request_type == "new_organization"
            else None
        ),
        new_organization_contact_email=None,
    )
    request.id = uuid.uuid4()
    request.created_at = _NOW
    request.reviewed_at = None
    request.reviewed_by = None
    request.user_id = None
    request.created_organization_id = None
    return request


_EXISTING_PAYLOAD = {
    "name": "Carlos da Silva",
    "email": "carlos@horizonteseguro.app",
    "password": "supersecret-1234",
    "roles": ["shelter_manager"],
    "phone": "82999999999",
}


class TestRegistrationRequests:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_create_request_with_existing_organization(self):
        organization = _organization()
        session = _Session(
            organizations={organization.id: organization},
            scalar_results=[None, None],
        )
        app.dependency_overrides[get_session] = _override(session)

        with patch(
            "controllers.registration_request.hash_password", return_value="$hashed"
        ):
            response = TestClient(app).post(
                "/registration-requests/existing-organization",
                json={**_EXISTING_PAYLOAD, "organization_id": str(organization.id)},
            )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending"
        assert body["request_type"] == "existing_organization"
        assert body["organization_id"] == str(organization.id)
        request = next(
            obj for obj in session.added if isinstance(obj, RegistrationRequest)
        )
        assert request.password_hash == "$hashed"

    def test_create_request_with_new_organization(self):
        session = _Session(scalar_results=[None, None, None, None])
        app.dependency_overrides[get_session] = _override(session)

        with patch(
            "controllers.registration_request.hash_password", return_value="$hashed"
        ):
            response = TestClient(app).post(
                "/registration-requests/new-organization",
                json={
                    **_EXISTING_PAYLOAD,
                    "organization_name": "Nova Defesa Civil",
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending"
        assert body["request_type"] == "new_organization"
        assert body["new_organization_name"] == "Nova Defesa Civil"
        assert body["new_organization_type"] == "shelter_operator"

    def test_public_request_rejects_dev_role(self):
        organization = _organization()
        session = _Session(organizations={organization.id: organization})
        app.dependency_overrides[get_session] = _override(session)

        response = TestClient(app).post(
            "/registration-requests/existing-organization",
            json={
                **_EXISTING_PAYLOAD,
                "email": "dev@horizonteseguro.app",
                "roles": ["dev"],
                "organization_id": str(organization.id),
            },
        )

        assert response.status_code == 422

    def test_existing_organization_request_rejects_ambiguous_payload(self):
        organization = _organization()
        session = _Session(organizations={organization.id: organization})
        app.dependency_overrides[get_session] = _override(session)

        response = TestClient(app).post(
            "/registration-requests/existing-organization",
            json={
                **_EXISTING_PAYLOAD,
                "organization_id": str(organization.id),
                "organization_name": "Nao deveria vir aqui",
            },
        )

        assert response.status_code == 422

    def test_new_organization_request_rejects_ambiguous_payload(self):
        session = _Session()
        app.dependency_overrides[get_session] = _override(session)

        response = TestClient(app).post(
            "/registration-requests/new-organization",
            json={
                **_EXISTING_PAYLOAD,
                "organization_name": "Nova Defesa Civil",
                "organization_id": str(uuid.uuid4()),
            },
        )

        assert response.status_code == 422

    def test_duplicate_email_in_users_returns_409(self):
        organization = _organization()
        session = _Session(
            organizations={organization.id: organization},
            scalar_results=[_user()],
        )
        app.dependency_overrides[get_session] = _override(session)

        response = TestClient(app).post(
            "/registration-requests/existing-organization",
            json={**_EXISTING_PAYLOAD, "organization_id": str(organization.id)},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "email already registered"

    def test_duplicate_pending_email_returns_409(self):
        organization = _organization()
        pending = _registration_request(organization_id=organization.id)
        session = _Session(
            organizations={organization.id: organization},
            scalar_results=[None, pending],
        )
        app.dependency_overrides[get_session] = _override(session)

        response = TestClient(app).post(
            "/registration-requests/existing-organization",
            json={**_EXISTING_PAYLOAD, "organization_id": str(organization.id)},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == "registration request already pending"

    def test_unknown_organization_returns_404(self):
        session = _Session()
        app.dependency_overrides[get_session] = _override(session)

        response = TestClient(app).post(
            "/registration-requests/existing-organization",
            json={**_EXISTING_PAYLOAD, "organization_id": str(uuid.uuid4())},
        )

        assert response.status_code == 404

    def test_list_requires_authorized_role(self):
        session = _Session()
        app.dependency_overrides[get_session] = _override(session)

        response = TestClient(app).get(
            "/registration-requests",
            headers=auth_headers("shelter_manager"),
        )

        assert response.status_code == 403

    def test_approve_existing_organization_by_allowed_roles(self):
        for role in ("dev", "crisis_manager"):
            organization = _organization()
            request = _registration_request(organization_id=organization.id)
            session = _Session(
                organizations={organization.id: organization},
                requests={request.id: request},
                scalar_results=[None, None],
            )
            app.dependency_overrides[get_session] = _override(session)

            with patch(
                "controllers.registration_request.send_registration_approved_email"
            ) as send_email:
                response = TestClient(app).post(
                    f"/registration-requests/{request.id}/approve",
                    headers=auth_headers(role),
                )

            assert response.status_code == 200, (role, response.json())
            body = response.json()
            assert body["status"] == "approved"
            assert body["user_id"] is not None
            user = next(obj for obj in session.added if isinstance(obj, User))
            assert user.organization_id == organization.id
            assert user.verified is True
            send_email.assert_called_once_with(
                to="carlos@horizonteseguro.app",
                name="Carlos da Silva",
            )

    def test_shelter_manager_cannot_approve(self):
        organization = _organization()
        request = _registration_request(organization_id=organization.id)
        session = _Session(
            organizations={organization.id: organization},
            requests={request.id: request},
        )
        app.dependency_overrides[get_session] = _override(session)

        response = TestClient(app).post(
            f"/registration-requests/{request.id}/approve",
            headers=auth_headers("shelter_manager"),
        )

        assert response.status_code == 403

    def test_approve_new_organization_creates_organization_and_user(self):
        request = _registration_request(request_type="new_organization")
        session = _Session(
            requests={request.id: request},
            scalar_results=[None, None, None, None],
        )
        app.dependency_overrides[get_session] = _override(session)

        with patch(
            "controllers.registration_request.send_registration_approved_email"
        ) as send_email:
            response = TestClient(app).post(
                f"/registration-requests/{request.id}/approve",
                headers=auth_headers("dev"),
            )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "approved"
        assert body["created_organization_id"] is not None
        organization = next(
            obj for obj in session.added if isinstance(obj, Organization)
        )
        user = next(obj for obj in session.added if isinstance(obj, User))
        assert organization.name == "Nova Defesa Civil"
        assert user.organization_id == organization.id
        assert user.verified is True
        send_email.assert_called_once_with(
            to="carlos@horizonteseguro.app",
            name="Carlos da Silva",
        )

    def test_email_failure_does_not_rollback_approval(self):
        organization = _organization()
        request = _registration_request(organization_id=organization.id)
        session = _Session(
            organizations={organization.id: organization},
            requests={request.id: request},
            scalar_results=[None, None],
        )
        app.dependency_overrides[get_session] = _override(session)

        with patch(
            "controllers.registration_request.send_registration_approved_email",
            side_effect=RuntimeError("resend down"),
        ):
            response = TestClient(app).post(
                f"/registration-requests/{request.id}/approve",
                headers=auth_headers("dev"),
            )

        assert response.status_code == 200
        assert response.json()["status"] == "approved"
        assert session.committed is True
        assert session.rolled_back is False

    def test_reject_request_does_not_create_user_or_organization(self):
        request = _registration_request(request_type="new_organization")
        session = _Session(requests={request.id: request})
        app.dependency_overrides[get_session] = _override(session)

        with patch(
            "controllers.registration_request.send_registration_approved_email"
        ) as send_email:
            response = TestClient(app).post(
                f"/registration-requests/{request.id}/reject",
                headers=auth_headers("crisis_manager"),
            )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        assert not any(isinstance(obj, User) for obj in session.added)
        assert not any(isinstance(obj, Organization) for obj in session.added)
        send_email.assert_not_called()
