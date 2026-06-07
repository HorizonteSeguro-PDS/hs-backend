"""Dev database seeder. Run after `alembic upgrade head`.

Usage:
    python scripts/seed.py
    python scripts/seed.py --reset   # delete seeded rows first

Creates:
  - 4 single-role users (dev / crisis_manager / shelter_manager / sheltered)
  - 1 multi-role user (crisis_manager + shelter_manager) — for testing
    that require_role accepts ANY-match across the user's roles
  - 5 sample crises authored by the dev user, scoped to the crisis_manager
    via users_crises

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
from domain.models.user_role import UserRole  # noqa: E402
from domain.models.users_crises import UsersCrises  # noqa: E402
from services.auth_service import (  # noqa: E402
    create_access_token,
    grant_role,
    hash_password,
)
from utils.database import SessionLocal  # noqa: E402

DEFAULT_PASSWORD = "admin1234"

USERS_SPEC: list[dict] = [
    {
        "email": "admin@horizonteseguro.app",
        "name": "Admin Dev",
        "roles": [Role.DEV],
    },
    {
        "email": "gestor.crise@horizonteseguro.app",
        "name": "Gestor de Crise",
        "roles": [Role.CRISIS_MANAGER],
    },
    {
        "email": "gestor.abrigo@horizonteseguro.app",
        "name": "Gestor de Abrigo",
        "roles": [Role.SHELTER_MANAGER],
    },
    {
        "email": "abrigado@horizonteseguro.app",
        "name": "Pessoa Abrigada",
        "roles": [Role.SHELTERED],
    },
    {
        "email": "multi@horizonteseguro.app",
        "name": "Multi-role Tester",
        "roles": [Role.CRISIS_MANAGER, Role.SHELTER_MANAGER],
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
    seeded_user_rows = session.scalars(
        select(User).where(User.email.in_(SEEDED_USER_EMAILS))
    ).all()
    seeded_user_ids = [u.id for u in seeded_user_rows]

    session.execute(delete(Crisis).where(Crisis.name.in_(SEEDED_CRISIS_NAMES)))
    if seeded_user_ids:
        session.execute(
            delete(UsersCrises).where(UsersCrises.user_id.in_(seeded_user_ids))
        )
        session.execute(delete(UserRole).where(UserRole.user_id.in_(seeded_user_ids)))
        session.execute(delete(User).where(User.id.in_(seeded_user_ids)))
    session.commit()
    print("[seed] reset: deleted seeded users, crises and grants.")


def seed_users(session) -> dict[str, tuple[User, list[Role]]]:
    """Get-or-create seed users keyed by email. Returns {email: (user, roles)}."""
    out: dict[str, tuple[User, list[Role]]] = {}
    for spec in USERS_SPEC:
        existing = session.scalar(select(User).where(User.email == spec["email"]))
        if existing is not None:
            print(f"[seed] user {spec['email']} already exists.")
            # Ensure roles match the spec (idempotent: grant_role no-ops on dup)
            for role in spec["roles"]:
                grant_role(session, user_id=existing.id, role=role)
            out[spec["email"]] = (existing, list(spec["roles"]))
            continue

        user = User(
            organization_id=None,
            name=spec["name"],
            email=spec["email"],
            phone=None,
            password_hash=hash_password(DEFAULT_PASSWORD),
            verified=True,
        )
        session.add(user)
        session.flush()
        for role in spec["roles"]:
            grant_role(session, user_id=user.id, role=role)
        out[spec["email"]] = (user, list(spec["roles"]))
        role_label = ",".join(r.value for r in spec["roles"])
        print(f"[seed] created user {spec['email']} (roles={role_label})")
    return out


def seed_crises(session, *, author_id) -> list[Crisis]:
    """Insert sample crises owned by `author_id`. Returns the full list of
    seed crises (existing + newly inserted)."""
    rows: list[Crisis] = []
    inserted = 0
    for data in CRISES_SPEC:
        existing = session.scalar(select(Crisis).where(Crisis.name == data["name"]))
        if existing is not None:
            rows.append(existing)
            continue
        crisis = Crisis(**data, created_by=author_id)
        session.add(crisis)
        session.flush()
        rows.append(crisis)
        inserted += 1
    if inserted:
        print(f"[seed] {inserted} new crises created.")
    else:
        print("[seed] all sample crises already exist.")
    return rows


def grant_scope(session, *, crisis_manager_user_id, crises: list[Crisis]) -> None:
    """Populate users_crises for the crisis_manager seed user, idempotent."""
    granted = 0
    for c in crises:
        existing = session.scalar(
            select(UsersCrises).where(
                UsersCrises.user_id == crisis_manager_user_id,
                UsersCrises.crisis_id == c.id,
            )
        )
        if existing is not None:
            continue
        session.add(UsersCrises(user_id=crisis_manager_user_id, crisis_id=c.id))
        granted += 1
    if granted:
        print(f"[seed] granted scope on {granted} crises to crisis_manager.")


def print_credentials(users: dict[str, tuple[User, list[Role]]]) -> None:
    print()
    print("=== Usuarios seeded ===")
    print(f"Senha (para todos): {DEFAULT_PASSWORD}")
    print("Se a senha nao funcionar, rode o seed com --reset.\n")
    print("=== JWTs (validos por 24h) ===")
    for spec in USERS_SPEC:
        user, roles = users[spec["email"]]
        token, _ = create_access_token(user_id=user.id, roles=roles)
        role_label = ",".join(r.value for r in roles)
        print(f"\n[{role_label}]")
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

        dev_user, _ = users["admin@horizonteseguro.app"]
        crisis_mgr, _ = users["gestor.crise@horizonteseguro.app"]

        crises = seed_crises(session, author_id=dev_user.id)
        session.commit()

        grant_scope(
            session,
            crisis_manager_user_id=crisis_mgr.id,
            crises=crises,
        )
        session.commit()

        print_credentials(users)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete previously-seeded users, crises and grants before inserting.",
    )
    args = parser.parse_args()
    return run(reset_first=args.reset)


if __name__ == "__main__":
    sys.exit(main())
