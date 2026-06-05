from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from utils.database import SessionLocal


def get_session() -> Generator[Session, None, None]:
    try:
        db = SessionLocal()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database not configured",
        ) from exc
    try:
        yield db
    finally:
        db.close()
