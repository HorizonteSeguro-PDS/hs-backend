"""Authentication services: password hashing, JWT minting, role grants."""

from datetime import datetime, timezone
from uuid import UUID

import bcrypt
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from domain.auth.enums import Role
from domain.models.user import User
from domain.models.user_role import UserRole


# --- crypto --- #


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (cost 12)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode(
        "utf-8"
    )


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time check that `plain` matches a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash (e.g. the "!disabled!" placeholder from migration 0004).
        return False


# --- JWT --- #


def create_access_token(
    *,
    user_id: UUID,
    roles: list[Role],
    organization_id: UUID | None = None,
) -> tuple[str, int]:
    """
    Mint a JWT for a user. Returns (token, expires_in_seconds).

    The `sub` claim carries the user id and the `roles` claim carries the
    list of role strings — same shape that `decode_jwt` expects.
    """
    expires_in = settings.jwt_expires_hours * 3600
    payload = {
        "sub": str(user_id),
        "roles": [r.value for r in roles],
        "exp": int(datetime.now(timezone.utc).timestamp()) + expires_in,
    }
    if organization_id is not None:
        payload["organization_id"] = str(organization_id)
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


# --- roles --- #


def get_user_roles(session: Session, user_id: UUID) -> list[Role]:
    """Return the roles assigned to a user, ordered deterministically."""
    rows = session.scalars(
        select(UserRole.role).where(UserRole.user_id == user_id)
    ).all()
    roles: list[Role] = []
    for row in rows:
        try:
            roles.append(row if isinstance(row, Role) else Role(row))
        except ValueError:
            continue
    return sorted(roles, key=lambda r: r.value)


def grant_role(session: Session, *, user_id: UUID, role: Role) -> None:
    """
    Grant a single role to a user. Idempotent — duplicates are skipped via PK.

    Does NOT commit; caller controls the transaction.
    """
    existing = session.scalar(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role == role)
    )
    if existing is not None:
        return
    session.add(UserRole(user_id=user_id, role=role))
    session.flush()


# --- permissions matrix --- #

_CREATE_RULES: dict[Role, set[Role]] = {
    Role.DEV: {Role.DEV, Role.CRISIS_MANAGER, Role.SHELTER_MANAGER},
    Role.CRISIS_MANAGER: {Role.SHELTER_MANAGER},
    Role.SHELTER_MANAGER: set(),
}


def can_create_role(actor_roles: list[Role] | set[Role], target_role: Role) -> bool:
    """Return True if any of `actor_roles` is authorized to create `target_role`."""
    return any(target_role in _CREATE_RULES.get(role, set()) for role in actor_roles)


def can_create_roles(
    actor_roles: list[Role] | set[Role], target_roles: list[Role] | set[Role]
) -> bool:
    """Return True if `actor_roles` can create every role in `target_roles`."""
    return all(can_create_role(actor_roles, r) for r in target_roles)


# --- authentication --- #


def authenticate(
    session: Session, *, email: str, password: str
) -> tuple[User, list[Role]] | None:
    """
    Verify credentials and resolve the user's roles.

    Returns (user, roles) on success, None otherwise. Returns None for both
    unknown email and bad password — same error surfaced to the client to
    avoid leaking which emails are registered.
    """
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    roles = get_user_roles(session, user.id)
    return user, roles
