# Inventory endpoints — guia de implementação

Esta PR (`feat/shelter-inventory-and-categories`) entrega toda a infraestrutura
(migrations + models + schemas + repositories + services + seed + tests) pro
gerenciamento de inventário de abrigos. **Os controllers ficaram de fora de
propósito** — esta doc lista os endpoints sugeridos e como cada um deve costurar.

## Resumo do RBAC

| Endpoint | Auth | Roles |
|---|---|---|
| `GET /resource-categories` | público | — |
| `GET /resource-categories/search?q=...` | público | — |
| `GET /resource-categories/{id}` | público | — |
| `POST /resource-categories` | autenticado | dev, crisis_manager |
| `PATCH /resource-categories/{id}` | autenticado | dev, crisis_manager |
| `GET /shelters/{id}/inventory` | autenticado | dev, crisis_manager, shelter_manager |
| `GET /shelters/{id}/inventory/movements` | autenticado | dev, crisis_manager, shelter_manager |
| `POST /shelters/{id}/inventory/movements` | autenticado | dev, crisis_manager, shelter_manager |

Lembre: `require_role("dev", "crisis_manager", "shelter_manager")` aceita
qualquer das três. Pra writes restritos a dev+crisis_manager, use só esses dois.

---

## Endpoints sugeridos — esqueleto

Crie `controllers/resource_category.py` e `controllers/inventory.py` (ou tudo
em um, conforme convenção). Lembre de incluir os routers em `main.py`.

### `controllers/resource_category.py`

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.inventory.schemas import (
    ResourceCategoryCreateRequest,
    ResourceCategoryRead,
    ResourceCategoryUpdateRequest,
)
from repositories import ResourceCategoryRepository
from services import ResourceCategoryService

router = APIRouter(prefix="/resource-categories", tags=["resource-categories"])

_WriteDep = Annotated[
    CurrentUser, Depends(require_role("dev", "crisis_manager"))
]
_SessionDep = Annotated[Session, Depends(get_session)]


# Reads são PÚBLICOS (nenhum require_role aqui).

@router.get("", response_model=list[ResourceCategoryRead])
def list_categories(session: _SessionDep) -> list[ResourceCategoryRead]:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    return service.list_all()


@router.get("/search", response_model=list[ResourceCategoryRead])
def search_categories(
    session: _SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[ResourceCategoryRead]:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    return service.search(q, limit=limit)


@router.get("/{category_id}", response_model=ResourceCategoryRead)
def get_category(
    category_id: UUID, session: _SessionDep
) -> ResourceCategoryRead:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    return service.get(category_id)


@router.post(
    "", response_model=ResourceCategoryRead, status_code=status.HTTP_201_CREATED
)
def create_category(
    payload: ResourceCategoryCreateRequest,
    session: _SessionDep,
    _user: _WriteDep,
) -> ResourceCategoryRead:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    category = service.create(payload)
    session.commit()
    return category


@router.patch("/{category_id}", response_model=ResourceCategoryRead)
def update_category(
    category_id: UUID,
    payload: ResourceCategoryUpdateRequest,
    session: _SessionDep,
    _user: _WriteDep,
) -> ResourceCategoryRead:
    service = ResourceCategoryService(ResourceCategoryRepository(session))
    category = service.update(category_id, payload)
    session.commit()
    return category
```

### `controllers/inventory.py`

```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.inventory.schemas import (
    InventoryItemRead,
    InventoryMovementCreateRequest,
    InventoryMovementRead,
    InventoryMovementRecordedResponse,
)
from domain.schemas.enums import MovementReason
from schemas.pagination import Page, PaginationParams, pagination_params
from services import InventoryService

router = APIRouter(prefix="/shelters", tags=["inventory"])

_AnyAuth = Annotated[
    CurrentUser,
    Depends(require_role("dev", "crisis_manager", "shelter_manager")),
]
_SessionDep = Annotated[Session, Depends(get_session)]


@router.get(
    "/{shelter_id}/inventory",
    response_model=list[InventoryItemRead],
)
def list_inventory(
    shelter_id: UUID,
    session: _SessionDep,
    _user: _AnyAuth,
) -> list[InventoryItemRead]:
    return InventoryService(session).list_inventory_for_shelter(
        shelter_id=shelter_id
    )


@router.get(
    "/{shelter_id}/inventory/movements",
    response_model=Page[InventoryMovementRead],
)
def list_movements(
    shelter_id: UUID,
    session: _SessionDep,
    _user: _AnyAuth,
    pagination: Annotated[PaginationParams, Depends(pagination_params)],
    category_id: Annotated[UUID | None, Query()] = None,
    reason: Annotated[MovementReason | None, Query()] = None,
) -> Page[InventoryMovementRead]:
    return InventoryService(session).list_movements_for_shelter(
        pagination,
        shelter_id=shelter_id,
        category_id=category_id,
        reason=reason,
    )


@router.post(
    "/{shelter_id}/inventory/movements",
    response_model=InventoryMovementRecordedResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_movement(
    shelter_id: UUID,
    payload: InventoryMovementCreateRequest,
    session: _SessionDep,
    user: _AnyAuth,
) -> InventoryMovementRecordedResponse:
    # InsufficientInventoryError já é HTTPException(400) — FastAPI propaga.
    result = InventoryService(session).record_movement(
        shelter_id=shelter_id,
        actor_id=user.id,
        payload=payload,
    )
    session.commit()
    return result
```

---

## Pontos de atenção

1. **400 quando saldo ficaria negativo**: `InventoryService.record_movement`
   levanta `InsufficientInventoryError` (subclasse de `HTTPException` com
   status 400). Controller não precisa fazer try/except — FastAPI propaga.

2. **Categoria inexistente no movement**: se o frontend passar `category_id`
   inválido, o INSERT vai violar FK e o Postgres devolve erro de integridade.
   Pra mensagem mais amigável, vale o controller validar `service.categories.get(...)`
   antes e devolver 404 customizado. Opcional pra MVP.

3. **`audit_event`**: cada `inventory_movement` JÁ é um log imutável. Se quiser
   também registrar no `audit_log` polimórfico (`entity_type=INVENTORY_MOVEMENT`),
   adicione um valor no PG enum `audit_entity_type` (não tem ainda) e chame
   `audit_event(...)` no controller após o commit.

4. **Tests**: o padrão é o mesmo do `test_shelter_crud.py` — `dependency_overrides`
   na session, payloads sem necessidade de DB real. Use o `_session_factory`
   estilo já em uso. Pros endpoints públicos (GETs de categoria), passe sem header.

5. **Search no front**: o endpoint `GET /resource-categories/search?q=...`
   retorna até 20 resultados ordenados por `name`. Implementa o fluxo
   "search-and-add" que discutimos — front mostra resultados; se nada bater,
   permite criar nova categoria via POST.

---

## Exemplo de payload — POST /shelters/{id}/inventory/movements

```json
{
    "category_id": "fa6c2c0e-1234-5678-90ab-cdef01234567",
    "direction": "in",
    "quantity": 100,
    "reason": "donation",
    "source": "Doação Supermercado Líder",
    "notes": "Validade 2025-12-01"
}
```

Resposta:
```json
{
    "movement": {
        "id": "...",
        "shelter_id": "...",
        "category_id": "fa6c2c0e-...",
        "direction": "in",
        "quantity": 100,
        "reason": "donation",
        "source": "Doação Supermercado Líder",
        "notes": "Validade 2025-12-01",
        "created_by": "...",
        "created_at": "2026-06-08T13:24:01Z"
    },
    "inventory_after": 100
}
```
