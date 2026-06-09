import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from domain.models.resource_category import ResourceCategory
from domain.schemas.enums import LotCategory, ResourceUnit
from repositories import ResourceCategoryRepository


def _create_tables(engine) -> None:
    ResourceCategory.__table__.create(engine)


def _make_category(
    name: str, unit: ResourceUnit = ResourceUnit.UNIDADE
) -> ResourceCategory:
    return ResourceCategory(
        id=uuid.uuid4(),
        name=name,
        unit=unit,
        lot_category=LotCategory.OPERACAO,
        description=None,
    )


def test_get_by_name_finds_exact_match():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        cat = _make_category("cobertor")
        session.add(cat)
        session.commit()

        repo = ResourceCategoryRepository(session)
        assert repo.get_by_name("cobertor").id == cat.id
        assert repo.get_by_name("Cobertor") is None  # case-sensitive


def test_search_substring_match():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        session.add_all(
            [
                _make_category("cobertor"),
                _make_category("cobertor casal"),
                _make_category("colchao"),
                _make_category("agua_potavel", ResourceUnit.L),
            ]
        )
        session.commit()

        repo = ResourceCategoryRepository(session)
        # SQLite ilike behaves like LIKE; case-insensitive
        results = repo.search("cobert")
        names = {r.name for r in results}
        assert names == {"cobertor", "cobertor casal"}

        results = repo.search("agua")
        assert {r.name for r in results} == {"agua_potavel"}


def test_search_respects_limit():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        for i in range(10):
            session.add(_make_category(f"item_{i}"))
        session.commit()

        repo = ResourceCategoryRepository(session)
        results = repo.search("item", limit=3)
        assert len(results) == 3


def test_list_returns_all_categories():
    engine = create_engine("sqlite:///:memory:")
    _create_tables(engine)

    with Session(engine) as session:
        for name in ("a", "b", "c"):
            session.add(_make_category(name))
        session.commit()

        repo = ResourceCategoryRepository(session)
        assert repo.count() == 3
        assert len(repo.list()) == 3
