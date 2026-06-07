"""Authentication services: password hashing, JWT minting, role resolution."""

from datetime import datetime, timezone
from uuid import UUID

import bcrypt
from jose import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from domain.auth.enums import Role
from domain.models.role import Role as RoleModel
from domain.models.user import User
from domain.schemas.enums import RoleScope


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


def create_access_token(*, user_id: UUID, role: Role) -> tuple[str, int]:
    """
    Mint a JWT for a user. Returns (token, expires_in_seconds).

    The `sub` claim carries the user id and the `role` claim carries the role
    string — same shape that `decode_jwt` already expects.
    """
    expires_in = settings.jwt_expires_hours * 3600
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "exp": int(datetime.now(timezone.utc).timestamp()) + expires_in,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def ensure_role(session: Session, role: Role) -> RoleModel:
    """
    Get-or-create the row in `roles` that corresponds to the given Role enum.

    Idempotent: safe to call on every registration. The roles table is shared
    across the system so we use the enum value as the canonical `name`.
    Does NOT commit — caller controls the transaction.
    """
    existing = session.scalar(select(RoleModel).where(RoleModel.name == role.value))
    if existing is not None:
        return existing

    new_role = RoleModel(name=role.value, scope=RoleScope.GLOBAL, permissions=None)
    session.add(new_role)
    session.flush()
    return new_role


def authenticate(
    session: Session, *, email: str, password: str
) -> tuple[User, Role] | None:
    """
    Verify credentials and resolve the user's role enum.

    Returns (user, role) on success, None otherwise. Returns None for both
    unknown email and bad password — same error surfaced to the client to
    avoid leaking which emails are registered.
    """
    row = session.execute(
        select(User, RoleModel.name)
        .join(RoleModel, RoleModel.id == User.role_id)
        .where(User.email == email)
    ).first()
    if row is None:
        return None
    user, role_name = row
    if not verify_password(password, user.password_hash):
        return None
    try:
        role = Role(role_name)
    except ValueError:
        # Role in DB does not match any enum — should never happen in practice.
        return None
    return user, role
