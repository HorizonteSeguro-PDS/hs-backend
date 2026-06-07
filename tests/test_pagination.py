from schemas.pagination import Page, PaginationParams, calculate_pages


def test_pagination_params_defaults():
    params = PaginationParams()

    assert params.page == 1
    assert params.size == 10
    assert params.offset == 0
    assert params.limit == 10


def test_pagination_params_offset_and_limit():
    params = PaginationParams(page=3, size=25)

    assert params.offset == 50
    assert params.limit == 25


def test_calculate_pages():
    assert calculate_pages(total=0, size=10) == 0
    assert calculate_pages(total=5, size=10) == 1
    assert calculate_pages(total=20, size=10) == 2
    assert calculate_pages(total=21, size=10) == 3


def test_page_create():
    page = Page[int].create(
        items=[1, 2],
        total=21,
        params=PaginationParams(page=2, size=10),
    )

    assert page.model_dump() == {
        "items": [1, 2],
        "total": 21,
        "page": 2,
        "size": 10,
        "pages": 3,
    }
