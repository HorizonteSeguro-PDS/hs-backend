"""HTTP layer dos check-in / check-out — auth + dispatch + commit."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import controllers.shelter_stay as shelter_stay_controller
from dependencies.session import get_session
from main import app
from tests.conftest import auth_headers


_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _session_override():
    session = MagicMock()

    def override():
        yield session

    return override, session


class TestCheckInEndpoint:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_anonymous_blocked(self):
        override, _ = _session_override()
        app.dependency_overrides[get_session] = override
        response = TestClient(app).post(
            f"/shelters/{uuid.uuid4()}/check-ins",
            json={"name": "X", "cpf": "111.222.333-44"},
        )
        assert response.status_code == 401

    def test_dispatches_and_commits(self, monkeypatch):
        override, session = _session_override()
        shelter_id = uuid.uuid4()
        beneficiary_id = uuid.uuid4()
        captured = {}

        class FakeService:
            def __init__(self, session):
                self.session = session

            def check_in(self, *, shelter_id, payload):
                from domain.shelter_stay.schemas import (
                    BeneficiaryRead,
                    CheckInResponse,
                    ShelterStayRead,
                )

                captured["shelter_id"] = shelter_id
                captured["payload"] = payload
                return CheckInResponse(
                    beneficiary=BeneficiaryRead(
                        id=beneficiary_id,
                        name=payload.name,
                        cpf=payload.cpf,
                    ),
                    stay=ShelterStayRead(
                        id=uuid.uuid4(),
                        beneficiary_id=beneficiary_id,
                        shelter_id=shelter_id,
                        checked_in_at=_NOW,
                        checked_out_at=None,
                    ),
                    shelter_occupation=5,
                )

        monkeypatch.setattr(shelter_stay_controller, "ShelterStayService", FakeService)
        app.dependency_overrides[get_session] = override

        response = TestClient(app).post(
            f"/shelters/{shelter_id}/check-ins",
            json={
                "name": "Maria",
                "cpf": "111.222.333-44",
                "phone": "+5582988887777",
            },
            headers=auth_headers("shelter_manager"),
        )

        assert response.status_code == 201
        body = response.json()
        assert body["beneficiary"]["name"] == "Maria"
        assert body["shelter_occupation"] == 5
        assert captured["shelter_id"] == shelter_id
        assert captured["payload"].cpf == "111.222.333-44"
        session.commit.assert_called_once()


class TestCheckOutEndpoint:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_anonymous_blocked(self):
        override, _ = _session_override()
        app.dependency_overrides[get_session] = override
        response = TestClient(app).post(
            f"/shelters/{uuid.uuid4()}/check-outs",
            json={"cpf": "111.222.333-44"},
        )
        assert response.status_code == 401

    def test_dispatches_and_commits(self, monkeypatch):
        override, session = _session_override()
        shelter_id = uuid.uuid4()
        beneficiary_id = uuid.uuid4()
        captured = {}

        class FakeService:
            def __init__(self, session):
                self.session = session

            def check_out(self, *, shelter_id, payload):
                from domain.shelter_stay.schemas import (
                    BeneficiaryRead,
                    CheckOutResponse,
                    ShelterStayRead,
                )

                captured["shelter_id"] = shelter_id
                captured["payload"] = payload
                return CheckOutResponse(
                    beneficiary=BeneficiaryRead(
                        id=beneficiary_id,
                        name="Maria",
                        cpf=payload.cpf,
                    ),
                    stay=ShelterStayRead(
                        id=uuid.uuid4(),
                        beneficiary_id=beneficiary_id,
                        shelter_id=shelter_id,
                        checked_in_at=_NOW,
                        checked_out_at=_NOW,
                    ),
                    shelter_occupation=4,
                )

        monkeypatch.setattr(shelter_stay_controller, "ShelterStayService", FakeService)
        app.dependency_overrides[get_session] = override

        response = TestClient(app).post(
            f"/shelters/{shelter_id}/check-outs",
            json={"cpf": "111.222.333-44"},
            headers=auth_headers("shelter_manager"),
        )

        assert response.status_code == 200
        assert response.json()["shelter_occupation"] == 4
        assert captured["payload"].cpf == "111.222.333-44"
        session.commit.assert_called_once()
