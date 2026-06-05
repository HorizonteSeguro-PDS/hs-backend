"""Dev database seeder. Run after `alembic upgrade head`.

Usage:
    python scripts/seed.py

Not idempotent — running twice inserts duplicate rows.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from jose import jwt

from config import settings
from domain.auth.enums import Role

from domain.models.audit_log import AuditLog  # noqa: F401 — registers metadata
from domain.models.crisis import Crisis
from utils.database import SessionLocal

TEST_USERS = {
    "master": "11111111-1111-1111-1111-111111111111",
    "standard": "22222222-2222-2222-2222-222222222222",
    "oversight": "33333333-3333-3333-3333-333333333333",
}

SEED_AUTHOR_ID = UUID(TEST_USERS["standard"])

CRISES_SEED = [
    {
        "name": "Enchente no Vale do Taquari",
        "type": "flood",
        "state": "RS",
        "city": "Lajeado",
        "severity_initial": 4,
        "status": "active",
    },
    {
        "name": "Incêndio Florestal Chapada",
        "type": "fire",
        "state": "BA",
        "city": "Palmeiras",
        "severity_initial": 3,
        "status": "active",
    },
    {
        "name": "Deslizamento Serra Gaúcha",
        "type": "landslide",
        "state": "RS",
        "city": "Gramado",
        "severity_initial": 5,
        "status": "closed",
        "close_reason": "Área estabilizada e famílias reassentadas.",
        "closed_by": "22222222-2222-2222-2222-222222222222",
    },
    {
        "name": "Evento Atípico Nordeste",
        "type": "other",
        "state": "CE",
        "city": "Fortaleza",
        "severity_initial": 2,
        "status": "active",
    },
    {
        "name": "Enchente Zona Leste SP",
        "type": "flood",
        "state": "SP",
        "city": "São Paulo",
        "severity_initial": 4,
        "status": "active",
    },
]


def mint_jwt(user_id: str, role: Role) -> str:
    payload = {
        "sub": user_id,
        "role": role.value,
        "exp": int(datetime.now(timezone.utc).timestamp()) + 60 * 60 * 24,  # 24h
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def run() -> None:
    with SessionLocal() as session:
        for data in CRISES_SEED:
            crisis = Crisis(**data, created_by=SEED_AUTHOR_ID)
            session.add(crisis)
        session.commit()
        print(f"Seeded {len(CRISES_SEED)} crises.")

    print("\n=== JWTs de teste (válidos por 24h) ===")
    for role_name, uid in TEST_USERS.items():
        role = Role(role_name)
        token = mint_jwt(uid, role)
        print(f"\n[{role_name}]")
        print(f"  user_id: {uid}")
        print(f"  token:   {token}")
    print("\nUso: copie o token e cole no botão 'Authorize' do Swagger (/api/docs).")


if __name__ == "__main__":
    run()
