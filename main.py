import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from config import settings
from controllers.auth import router as auth_router
from controllers.crisis import router as crisis_router
from controllers.inventory import router as inventory_router
from controllers.organization import router as organization_router
from controllers.registration_request import router as registration_request_router
from controllers.resource_category import router as resource_category_router
from controllers.shelter import router as shelter_router
from controllers.shelter_spreadsheet import router as shelter_spreadsheet_router
from controllers.user import router as user_router

# Piggyback on uvicorn's configured error logger — `hs-backend` would have no
# handler attached and the message would silently drop on the floor.
logger = logging.getLogger("uvicorn.error")
DOCS_URL = "/api/docs"
OPENAPI_URL = "/api/openapi.json"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.getLogger("uvicorn.error").info("Swagger UI: %s", DOCS_URL)
    yield


app = FastAPI(
    title="hs-backend",
    docs_url=DOCS_URL,
    openapi_url=OPENAPI_URL,
    swagger_ui_oauth2_redirect_url=f"{DOCS_URL}/oauth2-redirect",
    lifespan=lifespan,
)

# --- CORS ---
# `allow_credentials` é False propositadamente: nosso auth é via JWT em
# Authorization header (não cookies). Isso permite usar "*" em allow_origins
# se a env CORS_ALLOWED_ORIGINS for "*". Se um dia migrarmos pra cookies,
# precisa flipar pra True E garantir que allow_origins é lista explícita
# (browsers rejeitam credentials com wildcard).
_cors_origins = settings.cors_allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)
logger.info("CORS allowed origins: %s", _cors_origins)

app.include_router(auth_router)
app.include_router(crisis_router)
app.include_router(inventory_router)
app.include_router(organization_router)
app.include_router(registration_request_router)
app.include_router(resource_category_router)
app.include_router(shelter_router)
app.include_router(shelter_spreadsheet_router)
app.include_router(user_router)


@app.exception_handler(OperationalError)
async def db_operational_error_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "database unavailable"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Logs the full traceback before returning the generic 500 — makes
    # debugging in dev infinitely easier without changing the HTTP contract.
    logger.exception("unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error", "error": type(exc).__name__},
    )
