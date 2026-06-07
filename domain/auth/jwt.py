from dataclasses import dataclass
from uuid import UUID

from jose import JWTError, jwt

from config import settings
from domain.auth.enums import Role


@dataclass
class CurrentUser:
    id: UUID
    roles: list[Role]


def decode_jwt(token: str) -> CurrentUser:
    """
    Decode the JWT and return the resolved user identity.

    The payload is expected to contain:
      - sub:   user id as string UUID
      - roles: list of role names (strings) — see Role enum
      - exp:   expiration epoch (validated by jose)
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        raw_roles = payload["roles"]
        if not isinstance(raw_roles, list):
            raise ValueError("'roles' claim must be a list")
        return CurrentUser(
            id=UUID(payload["sub"]),
            roles=[Role(r) for r in raw_roles],
        )
    except (JWTError, KeyError, ValueError) as e:
        raise ValueError(f"invalid token: {e}")
