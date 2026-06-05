import os


class _Settings:
    @property
    def jwt_secret(self) -> str:
        v = os.getenv("JWT_SECRET")
        if not v:
            raise RuntimeError("JWT_SECRET environment variable is required.")
        return v


settings = _Settings()
