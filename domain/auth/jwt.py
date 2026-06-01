from dataclasses import dataclass
from uuid import UUID

from jose import JWTError, jwt

from config import settings
from domain.auth.enums import Role


@dataclass
class CurrentUser:
    id: UUID
    role: Role


def decode_jwt(token: str) -> CurrentUser:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return CurrentUser(
            id=UUID(payload["sub"]),
            role=Role(payload["role"]),
        )
    except (JWTError, KeyError, ValueError) as e:
        raise ValueError(f"invalid token: {e}")
