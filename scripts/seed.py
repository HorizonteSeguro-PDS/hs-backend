"""Dev database seeder. Run after `alembic upgrade head`.

Usage:
    python scripts/seed.py

Not idempotent — running twice inserts duplicate rows.
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.audit.enums import AuditAction, AuditEntityType
from domain.crisis.enums import CrisisStatus, CrisisType
from domain.models.audit_log import AuditLog  # noqa: F401 — registers metadata
from domain.models.crisis import Crisis
from services.audit_service import audit_event
from utils.database import SessionLocal

SEED_AUTHOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

CRISES_SEED = [
    dict(
        name="Enchente no Vale do Taquari",
        type=CrisisType.FLOOD,
        state="RS",
        city="Lajeado",
        severity_initial=4,
        status=CrisisStatus.ACTIVE,
    ),
    dict(
        name="Incêndio Florestal Chapada",
        type=CrisisType.FIRE,
        state="BA",
        city="Palmeiras",
        severity_initial=3,
        status=CrisisStatus.ACTIVE,
    ),
    dict(
        name="Deslizamento Serra Gaúcha",
        type=CrisisType.LANDSLIDE,
        state="RS",
        city="Gramado",
        severity_initial=5,
        status=CrisisStatus.CLOSED,
        close_reason="Área estabilizada e famílias reassentadas.",
        closed_by=SEED_AUTHOR_ID,
    ),
    dict(
        name="Evento Atípico Nordeste",
        type=CrisisType.OTHER,
        state="CE",
        city="Fortaleza",
        severity_initial=2,
        status=CrisisStatus.ACTIVE,
    ),
]


def run() -> None:
    with SessionLocal() as session:
        for data in CRISES_SEED:
            crisis = Crisis(**data, created_by=SEED_AUTHOR_ID)
            session.add(crisis)
            session.flush()
            audit_event(
                session,
                entity_type=AuditEntityType.CRISIS.value,
                entity_id=crisis.id,
                action=AuditAction.CREATE.value,
                author_id=SEED_AUTHOR_ID,
                payload={"name": crisis.name, "type": crisis.type.value},
            )
        session.commit()
        print(f"Seeded {len(CRISES_SEED)} crises + audit log entries.")


if __name__ == "__main__":
    run()
