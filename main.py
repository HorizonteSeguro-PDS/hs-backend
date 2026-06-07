import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from controllers.auth import router as auth_router
from controllers.crisis import router as crisis_router
from controllers.shelter import router as shelter_router
from controllers.user import router as user_router

# Piggyback on uvicorn's configured error logger — `hs-backend` would have no
# handler attached and the message would silently drop on the floor.
logger = logging.getLogger("uvicorn.error")
DOCS_URL = "/api/docs"
LOCAL_SWAGGER_URL = f"http://127.0.0.1:8000{DOCS_URL}"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.getLogger("uvicorn.error").info("Swagger UI: %s", LOCAL_SWAGGER_URL)
    yield


app = FastAPI(title="hs-backend", docs_url=DOCS_URL, lifespan=lifespan)

app.include_router(auth_router)
app.include_router(crisis_router)
app.include_router(shelter_router)
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
