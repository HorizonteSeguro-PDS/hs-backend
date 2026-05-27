"""Database configuration shared by the app and Alembic."""

import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_database_url(default: str | None = None) -> str:
    """Return the configured database URL."""
    database_url = os.getenv("DATABASE_URL") or default
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")

    return database_url


_engine: Engine | None = None


def get_engine() -> Engine:
    """Create the SQLAlchemy engine lazily."""
    global _engine

    if _engine is None:
        _engine = create_engine(get_database_url())

    return _engine


class _LazySessionMaker(sessionmaker[Session]):
    def __call__(self, **local_kw: Any) -> Session:
        if self.kw.get("bind") is None:
            self.configure(bind=get_engine())

        return super().__call__(**local_kw)


SessionLocal = _LazySessionMaker(autocommit=False, autoflush=False)
