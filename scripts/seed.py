"""Dev database seeder. Run after `alembic upgrade head`.

Usage:
    python scripts/seed.py

Idempotent: re-running skips rows that already exist (matched by email for
users and by name for crises). Use `--reset` to wipe seeded rows first.

Creates:
  - 3 test users (one per role) with bcrypt-hashed passwords
  - 5 sample crises authored by the standard test user

Then prints fresh JWTs for each role so you can paste straight into Swagger
without going through POST /auth/login.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from domain.auth.enums import Role  # noqa: E402
from domain.crisis.enums import CrisisStatus, CrisisType  # noqa: E402
from domain.models.audit_log import AuditLog  # noqa: E402, F401 — registers metadata
from domain.models.crisis import Crisis  # noqa: E402
from domain.models.user import User  # noqa: E402
from services.auth_service import (  # noqa: E402
    create_access_token,
    ensure_role,
    hash_password,
)
from utils.database import SessionLocal  # noqa: E402

TEST_PASSWORD = "test1234"  # shared by all 3 seeded users — dev only

TEST_USERS_SPEC = [
    {
        "email": "master@test.local",
        "name": "Master Tester",
        "role": Role.MASTER,
    },
    {
        "email": "standard@test.local",
        "name": "Standard Tester",
        "role": Role.STANDARD,
    },
    {
        "email": "oversight@test.local",
        "name": "Oversight Tester",
        "role": Role.OVERSIGHT,
    },
]

CRISES_SPEC = [
    {
        "name": "Enchente no Vale do Taquari",
        "type": CrisisType.FLOOD,
        "state": "RS",
        "city": "Lajeado",
        "severity_initial": 4,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Incêndio Florestal Chapada",
        "type": CrisisType.FIRE,
        "state": "BA",
        "city": "Palmeiras",
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Deslizamento Serra Gaúcha",
        "type": CrisisType.LANDSLIDE,
        "state": "RS",
        "city": "Gramado",
        "severity_initial": 5,
        "status": CrisisStatus.CLOSED,
        "close_reason": "Área estabilizada e famílias reassentadas.",
    },
    {
        "name": "Evento Atípico Nordeste",
        "type": CrisisType.OTHER,
        "state": "CE",
        "city": "Fortaleza",
        "severity_initial": 2,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Enchente Zona Leste SP",
        "type": CrisisType.FLOOD,
        "state": "SP",
        "city": "São Paulo",
        "severity_initial": 4,
        "status": CrisisStatus.ACTIVE,
    },
]

SEEDED_USER_EMAILS = [u["email"] for u in TEST_USERS_SPEC]
SEEDED_CRISIS_NAMES = [c["name"] for c in CRISES_SPEC]


def reset(session) -> None:
    """Wipe rows previously inserted by this seeder. Safe to run repeatedly."""
    session.execute(delete(Crisis).where(Crisis.name.in_(SEEDED_CRISIS_NAMES)))
    session.execute(delete(User).where(User.email.in_(SEEDED_USER_EMAILS)))
    session.commit()
    print("[seed] reset: deleted seeded users and crises.")


def seed_users(session) -> dict[Role, User]:
    """Get-or-create test users keyed by role. Returns {role: user}."""
    by_role: dict[Role, User] = {}
    for spec in TEST_USERS_SPEC:
        existing = session.scalar(select(User).where(User.email == spec["email"]))
        if existing is not None:
            print(f"[seed] user {spec['email']} already exists.")
            by_role[spec["role"]] = existing
            continue

        role_row = ensure_role(session, spec["role"])
        user = User(
            role_id=role_row.id,
            organization_id=None,
            name=spec["name"],
            email=spec["email"],
            phone=None,
            password_hash=hash_password(TEST_PASSWORD),
            verified=True,
        )
        session.add(user)
        session.flush()
        by_role[spec["role"]] = user
        print(f"[seed] created user {spec['email']} (role={spec['role'].value})")
    return by_role


def seed_crises(session, *, author_id) -> int:
    """Insert sample crises owned by `author_id`. Skip if name already exists."""
    inserted = 0
    for data in CRISES_SPEC:
        existing = session.scalar(select(Crisis).where(Crisis.name == data["name"]))
        if existing is not None:
            continue
        session.add(Crisis(**data, created_by=author_id))
        inserted += 1
    return inserted


def print_jwts(users: dict[Role, User]) -> None:
    print("\n=== JWTs de teste (validos por 24h) ===")
    print(f"Senha de todos os usuarios seeded: {TEST_PASSWORD}\n")
    for role in (Role.MASTER, Role.STANDARD, Role.OVERSIGHT):
        user = users.get(role)
        if user is None:
            continue
        token, _ = create_access_token(user_id=user.id, role=role)
        print(f"[{role.value}]")
        print(f"  email:   {user.email}")
        print(f"  user_id: {user.id}")
        print(f"  token:   {token}\n")
    print("Uso: clica em 'Authorize' no Swagger (/api/docs) e cola: Bearer <token>")
    print("Ou faz POST /auth/login com email + senha pra obter um token novo.")


def run(reset_first: bool) -> int:
    with SessionLocal() as session:
        if reset_first:
            reset(session)

        users = seed_users(session)
        session.commit()

        author = users.get(Role.STANDARD)
        if author is None:
            print("[seed] ERROR: standard user not available to author crises.")
            return 1

        inserted = seed_crises(session, author_id=author.id)
        session.commit()
        if inserted:
            print(f"[seed] {inserted} new crises created.")
        else:
            print("[seed] all sample crises already exist.")

        print_jwts(users)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete previously-seeded users and crises before inserting.",
    )
    args = parser.parse_args()
    return run(reset_first=args.reset)


if __name__ == "__main__":
    sys.exit(main())
