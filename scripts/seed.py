"""Dev database seeder. Run after `alembic upgrade head`.

Usage:
    python scripts/seed.py
    python scripts/seed.py --reset   # delete seeded rows first

Creates:
  - 3 users — one per role (master / standard / oversight) — all under
    @horizonteseguro.app and sharing the password `admin1234`
  - 5 sample crises authored by the master user

Idempotent: re-running skips rows that already exist (matched by email for
users and by name for crises). Use --reset to wipe the seeded rows first.
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

DEFAULT_PASSWORD = "admin1234"

USERS_SPEC = [
    {
        "role": Role.MASTER,
        "email": "admin@horizonteseguro.app",
        "name": "Admin",
    },
    {
        "role": Role.STANDARD,
        "email": "standard@horizonteseguro.app",
        "name": "Standard Tester",
    },
    {
        "role": Role.OVERSIGHT,
        "email": "oversight@horizonteseguro.app",
        "name": "Oversight Tester",
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

SEEDED_USER_EMAILS = [u["email"] for u in USERS_SPEC]
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
    for spec in USERS_SPEC:
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
            password_hash=hash_password(DEFAULT_PASSWORD),
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


def print_credentials(users: dict[Role, User]) -> None:
    print()
    print("=== Usuarios seeded ===")
    print(f"Senha (para todos): {DEFAULT_PASSWORD}")
    print("Se a senha nao funcionar, rode o seed com --reset.\n")
    print("=== JWTs (validos por 24h) ===")
    for role in (Role.MASTER, Role.STANDARD, Role.OVERSIGHT):
        user = users.get(role)
        if user is None:
            continue
        token, _ = create_access_token(user_id=user.id, role=role)
        print(f"\n[{role.value}]")
        print(f"  email:   {user.email}")
        print(f"  user_id: {user.id}")
        print(f"  token:   {token}")
    print()
    print("Uso:")
    print("  - Cola o JWT em 'Authorize' no Swagger (/api/docs): Bearer <token>")
    print("  - Ou faz POST /auth/login com email+senha pra obter um token novo")


def run(reset_first: bool) -> int:
    with SessionLocal() as session:
        if reset_first:
            reset(session)

        users = seed_users(session)
        session.commit()

        master = users.get(Role.MASTER)
        if master is None:
            print("[seed] ERROR: master user not available to author crises.")
            return 1

        inserted = seed_crises(session, author_id=master.id)
        session.commit()
        if inserted:
            print(f"[seed] {inserted} new crises created.")
        else:
            print("[seed] all sample crises already exist.")

        print_credentials(users)
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
