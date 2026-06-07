import os


class _Settings:
    @property
    def jwt_secret(self) -> str:
        v = os.getenv("JWT_SECRET")
        if not v:
            raise RuntimeError("JWT_SECRET environment variable is required.")
        return v

    @property
    def jwt_algorithm(self) -> str:
        return os.getenv("JWT_ALGORITHM", "HS256")

    @property
    def jwt_expires_hours(self) -> int:
        return int(os.getenv("JWT_EXPIRES_HOURS", "24"))


settings = _Settings()
