import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from controllers.crisis import router as crisis_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.getLogger("uvicorn.error").info("Swagger UI: /api/docs")
    yield


app = FastAPI(title="hs-backend", docs_url="/api/docs", lifespan=lifespan)

app.include_router(crisis_router)


@app.exception_handler(OperationalError)
async def db_operational_error_handler(
    request: Request, exc: OperationalError
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "database unavailable"},
    )
