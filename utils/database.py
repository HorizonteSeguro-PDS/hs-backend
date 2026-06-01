"""Database configuration shared by the app and Alembic."""

import os
from pathlib import Path
from typing import Any

# Auto-load .env se existir; variáveis já definidas no shell têm precedência.
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker  # noqa: E402

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
