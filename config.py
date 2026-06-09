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

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Origins liberados pelo CORS.

        Lê de `CORS_ALLOWED_ORIGINS` (vírgula-separado). Default: localhost
        em portas comuns de dev (Next.js, Vite, CRA). Em produção, defina
        explicitamente os domínios — ex:
            CORS_ALLOWED_ORIGINS=https://hs-frontend.vercel.app,https://app.horizonteseguro.app

        Use `*` (sozinho) pra liberar tudo — só recomendado quando nao for
        usar credenciais (cookies/sessao). JWT em Authorization header funciona
        com `*`.
        """
        raw = os.getenv("CORS_ALLOWED_ORIGINS")
        if raw is None:
            return [
                "http://localhost:3000",
                "http://localhost:5173",
                "http://localhost:8080",
            ]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def cors_allow_origin_regex(self) -> str | None:
        """Regex opcional pra liberar origens dinâmicas (preview deploys).

        Ex: `CORS_ALLOW_ORIGIN_REGEX=https://hs-frontend-.*\\.vercel\\.app`
        libera todos os preview deploys da Vercel.
        """
        return os.getenv("CORS_ALLOW_ORIGIN_REGEX") or None

    @property
    def resend_api_key(self) -> str | None:
        return os.getenv("RESEND_API_KEY") or None

    @property
    def email_from(self) -> str:
        return os.getenv("EMAIL_FROM", "Horizonte Seguro <onboarding@resend.dev>")

    @property
    def app_frontend_url(self) -> str | None:
        return os.getenv("APP_FRONTEND_URL") or None


settings = _Settings()
