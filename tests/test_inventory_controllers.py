import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import controllers.inventory as inventory_controller
import controllers.resource_category as resource_category_controller
from dependencies.session import get_session
from main import app
from tests.conftest import auth_headers


_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _session_override(mock: MagicMock | None = None):
    def override():
        yield mock or MagicMock()

    return override


class TestResourceCategoryController:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_list_categories_is_public(self, monkeypatch):
        category_id = uuid.uuid4()

        class FakeResourceCategoryService:
            def __init__(self, repository):
                self.repository = repository

            def list_all(self):
                return [
                    {
                        "id": category_id,
                        "name": "cobertor",
                        "unit": "unidade",
                        "description": None,
                    }
                ]

        monkeypatch.setattr(
            resource_category_controller,
            "ResourceCategoryService",
            FakeResourceCategoryService,
        )
        app.dependency_overrides[get_session] = _session_override()

        response = TestClient(app).get("/resource-categories")

        assert response.status_code == 200
        assert response.json()[0]["id"] == str(category_id)

    def test_create_category_requires_allowed_role_and_commits(self, monkeypatch):
        session = MagicMock()
        captured = {}
        category_id = uuid.uuid4()

        class FakeResourceCategoryService:
            def __init__(self, repository):
                self.repository = repository

            def create(self, payload):
                captured["payload"] = payload
                return {
                    "id": category_id,
                    "name": payload.name,
                    "unit": payload.unit,
                    "description": payload.description,
                }

        monkeypatch.setattr(
            resource_category_controller,
            "ResourceCategoryService",
            FakeResourceCategoryService,
        )
        app.dependency_overrides[get_session] = _session_override(session)

        response = TestClient(app).post(
            "/resource-categories",
            json={"name": "agua", "unit": "L", "description": None},
            headers=auth_headers("crisis_manager"),
        )

        assert response.status_code == 201
        assert captured["payload"].name == "agua"
        session.commit.assert_called_once()


class TestInventoryController:
    def setup_method(self):
        app.dependency_overrides = {}

    def teardown_method(self):
        app.dependency_overrides = {}

    def test_list_inventory_returns_200_for_allowed_role(self, monkeypatch):
        shelter_id = uuid.uuid4()
        item_id = uuid.uuid4()
        category_id = uuid.uuid4()

        class FakeInventoryService:
            def __init__(self, session):
                self.session = session

            def list_inventory_for_shelter(self, *, shelter_id):
                return [
                    {
                        "id": item_id,
                        "shelter_id": shelter_id,
                        "category_id": category_id,
                        "quantity_current": 15,
                        "updated_at": _NOW,
                    }
                ]

        monkeypatch.setattr(
            inventory_controller,
            "InventoryService",
            FakeInventoryService,
        )
        app.dependency_overrides[get_session] = _session_override()

        response = TestClient(app).get(
            f"/shelters/{shelter_id}/inventory",
            headers=auth_headers("shelter_manager"),
        )

        assert response.status_code == 200
        assert response.json()[0]["quantity_current"] == 15

    def test_list_movements_accepts_filters_and_pagination(self, monkeypatch):
        shelter_id = uuid.uuid4()
        category_id = uuid.uuid4()
        captured = {}

        class FakeInventoryService:
            def __init__(self, session):
                self.session = session

            def list_movements_for_shelter(
                self,
                pagination,
                *,
                shelter_id,
                category_id=None,
                reason=None,
            ):
                captured["pagination"] = pagination
                captured["shelter_id"] = shelter_id
                captured["category_id"] = category_id
                captured["reason"] = reason
                return {
                    "items": [],
                    "total": 0,
                    "page": pagination.page,
                    "size": pagination.size,
                    "pages": 0,
                }

        monkeypatch.setattr(
            inventory_controller,
            "InventoryService",
            FakeInventoryService,
        )
        app.dependency_overrides[get_session] = _session_override()

        response = TestClient(app).get(
            (
                f"/shelters/{shelter_id}/inventory/movements"
                f"?category_id={category_id}&reason=donation&page=2&size=5"
            ),
            headers=auth_headers("crisis_manager"),
        )

        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "total": 0,
            "page": 2,
            "size": 5,
            "pages": 0,
        }
        assert captured["shelter_id"] == shelter_id
        assert captured["category_id"] == category_id
        assert captured["reason"].value == "donation"

    def test_record_movement_uses_authenticated_user_and_commits(self, monkeypatch):
        session = MagicMock()
        shelter_id = uuid.uuid4()
        category_id = uuid.uuid4()
        user_id = uuid.uuid4()
        captured = {}

        class FakeInventoryService:
            def __init__(self, session):
                self.session = session

            def record_movement(self, *, shelter_id, actor_id, payload):
                captured["shelter_id"] = shelter_id
                captured["actor_id"] = actor_id
                captured["payload"] = payload
                return {
                    "movement": {
                        "id": uuid.uuid4(),
                        "shelter_id": shelter_id,
                        "category_id": payload.category_id,
                        "direction": payload.direction,
                        "quantity": payload.quantity,
                        "reason": payload.reason,
                        "source": payload.source,
                        "notes": payload.notes,
                        "created_by": actor_id,
                        "created_at": _NOW,
                    },
                    "inventory_after": payload.quantity,
                }

        monkeypatch.setattr(
            inventory_controller,
            "InventoryService",
            FakeInventoryService,
        )
        app.dependency_overrides[get_session] = _session_override(session)

        response = TestClient(app).post(
            f"/shelters/{shelter_id}/inventory/movements",
            json={
                "category_id": str(category_id),
                "direction": "in",
                "quantity": 10,
                "reason": "donation",
                "source": "Doacao",
                "notes": None,
            },
            headers=auth_headers("shelter_manager", user_id=str(user_id)),
        )

        assert response.status_code == 201
        assert captured["shelter_id"] == shelter_id
        assert captured["actor_id"] == user_id
        assert captured["payload"].quantity == 10
        session.commit.assert_called_once()
