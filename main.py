import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logging.getLogger("uvicorn.error").info("Swagger UI: /api/docs")
    yield


app = FastAPI(title="hs-backend", docs_url="/api/docs", lifespan=lifespan)
