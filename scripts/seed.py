"""Dev database seeder. Run after `alembic upgrade head`.

Usage:
    python scripts/seed.py
    python scripts/seed.py --reset   # delete seeded rows first

Creates:
  - 3 single-role users (dev / crisis_manager / shelter_manager)
  - 1 multi-role user (crisis_manager + shelter_manager) — for testing
    that require_role accepts ANY-match across the user's roles
  - sample crises authored by the dev user, scoped to the crisis_manager
    via users_crises
  - sample shelters (with city/state/cep) and M:N crisis/shelter links
    via crises_shelters

Sheltered people are NOT modelled as USERs — they live in the BENEFICIARY
entity (created in a future PR with endpoints).

Idempotent: re-running skips rows that already exist (matched by email for
users, by name for crises/shelters and by pair for links). Use --reset to wipe
the seeded rows first.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from domain.auth.enums import Role  # noqa: E402
from domain.crisis.enums import CrisisStatus, CrisisType  # noqa: E402
from domain.models.audit_log import AuditLog  # noqa: E402, F401 — registers metadata
from domain.models.crises_shelters import CrisesShelters  # noqa: E402
from domain.models.crisis import Crisis  # noqa: E402
from domain.models.resource_category import ResourceCategory  # noqa: E402
from domain.models.shelter import Shelter  # noqa: E402
from domain.models.user import User  # noqa: E402
from domain.models.user_role import UserRole  # noqa: E402
from domain.models.users_crises import UsersCrises  # noqa: E402
from domain.schemas.enums import (  # noqa: E402
    ResourceUnit,
    ShelterStatus,
    ShelterType,
)
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
        "email": "multi@horizonteseguro.app",
        "name": "Multi-role Tester",
        "roles": [Role.CRISIS_MANAGER, Role.SHELTER_MANAGER],
    },
]

# Emails que foram seedados em iterações anteriores e que não fazem mais parte
# do USERS_SPEC. O --reset apaga essas linhas pra não deixarem órfãs no banco.
LEGACY_USER_EMAILS = ["abrigado@horizonteseguro.app"]

# Severity na escala nova 0-3:
#   0 = INATIVO, 1 = BAIXA, 2 = MÉDIA, 3 = ALTA
CRISES_SPEC = [
    {
        "name": "Enchente no Vale do Taquari",
        "type": CrisisType.FLOOD,
        "state": "RS",
        "city": "Lajeado",
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Enchente em Maceió",
        "type": CrisisType.FLOOD,
        "description": "Alagamentos em bairros ribeirinhos e necessidade de acolhimento emergencial.",
        "state": "AL",
        "city": "Maceió",
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Deslizamento no Recife",
        "type": CrisisType.LANDSLIDE,
        "description": "Deslizamento em área de encosta com famílias desalojadas.",
        "state": "PE",
        "city": "Recife",
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Estiagem Prolongada em Fortaleza",
        "type": CrisisType.OTHER,
        "description": "Seca/estiagem prolongada com restrição de abastecimento em comunidades vulneráveis.",
        "state": "CE",
        "city": "Fortaleza",
        "severity_initial": 2,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Incêndio Florestal Chapada",
        "type": CrisisType.FIRE,
        "state": "BA",
        "city": "Palmeiras",
        "severity_initial": 2,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Deslizamento Serra Gaúcha",
        "type": CrisisType.LANDSLIDE,
        "state": "RS",
        "city": "Gramado",
        "severity_initial": 3,
        "status": CrisisStatus.CLOSED,
        "close_reason": "Área estabilizada e famílias reassentadas.",
    },
    {
        "name": "Evento Atípico Nordeste",
        "type": CrisisType.OTHER,
        "state": "CE",
        "city": "Fortaleza",
        "severity_initial": 1,
        "status": CrisisStatus.ACTIVE,
    },
    {
        "name": "Enchente Zona Leste SP",
        "type": CrisisType.FLOOD,
        "state": "SP",
        "city": "São Paulo",
        "severity_initial": 3,
        "status": CrisisStatus.ACTIVE,
    },
]

SHELTERS_SPEC = [
    {
        "organization_id": None,
        "responsible_user_id": None,
        "created_by": None,
        "verified_by": None,
        "name": "Abrigo Comunitário Benedito Bentes",
        "address": "Rua da Esperança, 120",
        "neighborhood": "Benedito Bentes",
        "city": "Maceió",
        "state": "AL",
        "cep": "57084-000",
        "latitude": -9.5568,
        "longitude": -35.7327,
        "capacity": 80,
        "occupation": 32,
        "shelter_type": ShelterType.COMMUNITY_HOME,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    },
    {
        "organization_id": None,
        "responsible_user_id": None,
        "created_by": None,
        "verified_by": None,
        "name": "Escola Municipal Esperança",
        "address": "Avenida Principal, 450",
        "neighborhood": "Tabuleiro do Martins",
        "city": "Maceió",
        "state": "AL",
        "cep": "57081-100",
        "latitude": -9.5901,
        "longitude": -35.7585,
        "capacity": 150,
        "occupation": 74,
        "shelter_type": ShelterType.IMPROVISED_PUBLIC,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    },
    {
        "organization_id": None,
        "responsible_user_id": None,
        "created_by": None,
        "verified_by": None,
        "name": "Ginásio Poliesportivo Municipal",
        "address": "Rua do Esporte, 88",
        "neighborhood": "Centro",
        "city": "Salvador",
        "state": "BA",
        "cep": "40015-000",
        "latitude": -12.9714,
        "longitude": -38.5014,
        "capacity": 220,
        "occupation": 118,
        "shelter_type": ShelterType.IMPROVISED_PUBLIC,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    },
    {
        "organization_id": None,
        "responsible_user_id": None,
        "created_by": None,
        "verified_by": None,
        "name": "Centro de Apoio Humanitário Nordeste",
        "address": "Avenida Recife Solidário, 1000",
        "neighborhood": "Imbiribeira",
        "city": "Recife",
        "state": "PE",
        "cep": "51170-000",
        "latitude": -8.1087,
        "longitude": -34.9093,
        "capacity": 120,
        "occupation": 45,
        "shelter_type": ShelterType.INSTITUTIONAL,
        "status": ShelterStatus.ACTIVE,
        "verified": True,
    },
]

CRISIS_SHELTER_LINKS = {
    "Enchente em Maceió": [
        "Abrigo Comunitário Benedito Bentes",
        "Escola Municipal Esperança",
    ],
    "Deslizamento no Recife": [
        "Centro de Apoio Humanitário Nordeste",
    ],
    "Incêndio Florestal Chapada": [
        "Ginásio Poliesportivo Municipal",
        "Centro de Apoio Humanitário Nordeste",
    ],
}

CATEGORIES_SPEC: list[tuple[str, ResourceUnit, str]] = [
    ("agua_potavel", ResourceUnit.L, "Água potável engarrafada"),
    ("cobertor", ResourceUnit.UNIDADE, "Cobertor adulto"),
    ("colchao", ResourceUnit.UNIDADE, "Colchão de campanha"),
    (
        "kit_medico_basico",
        ResourceUnit.UNIDADE,
        "Curativo, antitérmico, soro fisiológico",
    ),
    (
        "kit_higiene_pessoal",
        ResourceUnit.UNIDADE,
        "Escova, pasta, sabonete, toalha",
    ),
    ("fralda_descartavel", ResourceUnit.UNIDADE, "Bebê — pacote"),
    ("fralda_geriatrica", ResourceUnit.UNIDADE, "Adulto — pacote"),
    ("absorvente", ResourceUnit.UNIDADE, "Pacote padrão"),
    (
        "alimento_nao_perecivel",
        ResourceUnit.KG,
        "Arroz, feijão, açúcar, óleo, etc.",
    ),
    ("racao_animal", ResourceUnit.KG, "Ração para cães e gatos"),
    ("doacao_dinheiro", ResourceUnit.REAL, "Doação em dinheiro pra logística"),
]

SEEDED_USER_EMAILS = [u["email"] for u in USERS_SPEC]
SEEDED_CRISIS_NAMES = [c["name"] for c in CRISES_SPEC]
SEEDED_SHELTER_NAMES = [s["name"] for s in SHELTERS_SPEC]
SEEDED_CATEGORY_NAMES = [name for name, _, _ in CATEGORIES_SPEC]


def reset(session) -> None:
    """Wipe rows previously inserted by this seeder. Safe to run repeatedly."""
    seeded_user_rows = session.scalars(
        select(User).where(User.email.in_(SEEDED_USER_EMAILS + LEGACY_USER_EMAILS))
    ).all()
    seeded_user_ids = [u.id for u in seeded_user_rows]
    seeded_crisis_rows = session.scalars(
        select(Crisis).where(Crisis.name.in_(SEEDED_CRISIS_NAMES))
    ).all()
    seeded_crisis_ids = [c.id for c in seeded_crisis_rows]
    seeded_shelter_rows = session.scalars(
        select(Shelter).where(Shelter.name.in_(SEEDED_SHELTER_NAMES))
    ).all()
    seeded_shelter_ids = [s.id for s in seeded_shelter_rows]

    if seeded_crisis_ids:
        session.execute(
            delete(CrisesShelters).where(
                CrisesShelters.crisis_id.in_(seeded_crisis_ids)
            )
        )
        session.execute(
            delete(UsersCrises).where(UsersCrises.crisis_id.in_(seeded_crisis_ids))
        )
    if seeded_shelter_ids:
        session.execute(
            delete(CrisesShelters).where(
                CrisesShelters.shelter_id.in_(seeded_shelter_ids)
            )
        )
        session.execute(delete(Shelter).where(Shelter.id.in_(seeded_shelter_ids)))
    if seeded_crisis_ids:
        session.execute(delete(Crisis).where(Crisis.id.in_(seeded_crisis_ids)))
    if seeded_user_ids:
        session.execute(
            delete(UsersCrises).where(UsersCrises.user_id.in_(seeded_user_ids))
        )
        session.execute(delete(UserRole).where(UserRole.user_id.in_(seeded_user_ids)))
        session.execute(delete(User).where(User.id.in_(seeded_user_ids)))
    # Resource categories are shared / referenced by inventory_items and
    # inventory_movements. Reset only the ones we seeded by name.
    session.execute(
        delete(ResourceCategory).where(ResourceCategory.name.in_(SEEDED_CATEGORY_NAMES))
    )
    session.commit()
    print("[seed] reset: deleted seeded users, crises, shelters, grants, categories.")


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


def seed_shelters(
    session,
    *,
    responsible_user_id,
    created_by,
    verified_by,
) -> list[Shelter]:
    """Insert sample shelters. Returns existing + newly inserted shelters."""
    rows: list[Shelter] = []
    inserted = 0
    for spec in SHELTERS_SPEC:
        existing = session.scalar(select(Shelter).where(Shelter.name == spec["name"]))
        if existing is not None:
            rows.append(existing)
            continue

        data = {
            **spec,
            "responsible_user_id": responsible_user_id,
            "created_by": created_by,
            "verified_by": verified_by if spec["verified"] else None,
        }
        shelter = Shelter(**data)
        session.add(shelter)
        session.flush()
        rows.append(shelter)
        inserted += 1
    if inserted:
        print(f"[seed] {inserted} new shelters created.")
    else:
        print("[seed] all sample shelters already exist.")
    return rows


def seed_categories(session) -> list[ResourceCategory]:
    """Get-or-create the curated taxonomy of resource categories.

    Idempotent: skip rows whose `name` already exists in the table.
    """
    inserted = 0
    rows: list[ResourceCategory] = []
    for name, unit, description in CATEGORIES_SPEC:
        existing = session.scalar(
            select(ResourceCategory).where(ResourceCategory.name == name)
        )
        if existing is not None:
            rows.append(existing)
            continue
        category = ResourceCategory(name=name, unit=unit, description=description)
        session.add(category)
        session.flush()
        rows.append(category)
        inserted += 1
    if inserted:
        print(f"[seed] {inserted} new resource categories created.")
    else:
        print("[seed] all sample resource categories already exist.")
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


def link_crises_shelters(
    session,
    *,
    crises: list[Crisis],
    shelters: list[Shelter],
) -> None:
    """Populate crises_shelters links for sample data, idempotent."""
    crises_by_name = {c.name: c for c in crises}
    shelters_by_name = {s.name: s for s in shelters}
    linked = 0

    for crisis_name, shelter_names in CRISIS_SHELTER_LINKS.items():
        crisis = crises_by_name.get(crisis_name)
        if crisis is None:
            raise RuntimeError(
                f"Seed link references unknown crisis: {crisis_name!r}. "
                "Check CRISIS_SHELTER_LINKS and CRISES_SPEC."
            )

        for shelter_name in shelter_names:
            shelter = shelters_by_name.get(shelter_name)
            if shelter is None:
                raise RuntimeError(
                    f"Seed link references unknown shelter: {shelter_name!r}. "
                    "Check CRISIS_SHELTER_LINKS and SHELTERS_SPEC."
                )

            existing = session.scalar(
                select(CrisesShelters).where(
                    CrisesShelters.crisis_id == crisis.id,
                    CrisesShelters.shelter_id == shelter.id,
                )
            )
            if existing is not None:
                continue

            session.add(
                CrisesShelters(
                    crisis_id=crisis.id,
                    shelter_id=shelter.id,
                )
            )
            linked += 1

    if linked:
        print(f"[seed] linked {linked} crisis/shelter pairs.")
    else:
        print("[seed] all crisis/shelter links already exist.")


def print_credentials(users: dict[str, tuple[User, list[Role]]]) -> None:
    print()
    print("=== Usuarios seeded ===")
    print(f"Senha (para todos): {DEFAULT_PASSWORD}")
    print("Se a senha nao funcionar, rode o seed com --reset.\n")
    print("=== JWTs (validos por 24h) ===")
    for spec in USERS_SPEC:
        user, roles = users[spec["email"]]
        token, _ = create_access_token(
            user_id=user.id,
            roles=roles,
            organization_id=user.organization_id,
        )
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
        try:
            if reset_first:
                reset(session)

            users = seed_users(session)
            session.commit()

            dev_user, _ = users["admin@horizonteseguro.app"]
            crisis_mgr, _ = users["gestor.crise@horizonteseguro.app"]
            shelter_mgr, _ = users["gestor.abrigo@horizonteseguro.app"]

            crises = seed_crises(session, author_id=dev_user.id)
            session.commit()

            shelters = seed_shelters(
                session,
                responsible_user_id=shelter_mgr.id,
                created_by=dev_user.id,
                verified_by=dev_user.id,
            )
            session.commit()

            grant_scope(
                session,
                crisis_manager_user_id=crisis_mgr.id,
                crises=crises,
            )
            link_crises_shelters(session, crises=crises, shelters=shelters)
            session.commit()

            seed_categories(session)
            session.commit()

            print_credentials(users)
        except Exception:
            session.rollback()
            raise
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete previously-seeded users, crises, shelters and grants before inserting.",
    )
    args = parser.parse_args()
    return run(reset_first=args.reset)


if __name__ == "__main__":
    sys.exit(main())
