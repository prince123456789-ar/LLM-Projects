from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ignore unknown env vars so a shared .env can contain provider-specific placeholders
    # without breaking backend startup.
    # When running locally via `saas/scripts/start-local.ps1`, cwd is `saas/backend`, but users
    # often edit `saas/.env`. Load both (backend/.env first, then repo-root/.env).
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "RealEstateAI"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = "change_me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    JWT_ALGORITHM: str = "HS512"
    JWT_ISSUER: str = "realestate-ai"
    JWT_AUDIENCE: str = "realestate-ai-api"

    DATABASE_URL: str = ""
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "real_estate_ai"

    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # Default to allow any origin for the website embed SDK. In production, set this
    # to an explicit allowlist of your domains.
    BACKEND_CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])
    ALLOWED_HOSTS: list[str] = Field(
        default_factory=lambda: [
            "*.onrender.com",
            "*.ngrok-free.app",
            "*.ngrok.app",
            "*.ngrok.io",
            "localhost",
            "127.0.0.1",
        ]
    )
    FRONTEND_URL: str = "http://localhost:3000"

    ENABLE_API_DOCS: bool = False
    ALLOW_PUBLIC_SIGNUP: bool = False

    WEBHOOK_SHARED_SECRET: str = ""
    WEBHOOK_MAX_SKEW_SECONDS: int = 300

    META_VERIFY_TOKEN: str = ""
    META_APP_SECRET: str = ""

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@realestate-ai.local"
    SMTP_USE_TLS: bool = True

    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = 30

    # API keys / plans
    API_KEY_PREFIX: str = "rea_"
    EMBED_KEY_PREFIX: str = "rep_"

    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID: str = ""
    # Optional plan-specific Stripe Price IDs (recommended).
    STRIPE_PRICE_ID_AGENCY: str = ""
    STRIPE_PRICE_ID_PRO: str = ""
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/billing/success"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/billing/cancel"

    # Frontend proxy target for single-origin browser traffic.
    BACKEND_INTERNAL_URL: str = "http://localhost:8000"

    # OAuth providers
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = ""

    # Crypto-agility switch to rotate algorithms/keys without code change.
    ZERO_TRUST_SIGNING_ALG: str = "HS512"

    @model_validator(mode="after")
    def _prod_guards(self):
        # Production hardening toggles.
        if self.ENVIRONMENT.lower() == "production":
            if self.ENABLE_API_DOCS:
                raise ValueError("ENABLE_API_DOCS must be false in production")
            if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be 32+ chars in production")
            if any(h == "*" for h in self.ALLOWED_HOSTS):
                raise ValueError('ALLOWED_HOSTS must not contain "*" in production')
        else:
            # Developer convenience: avoid ngrok/preview "Invalid host header" issues.
            # (Do NOT use wildcard hosts in production.)
            if not self.ALLOWED_HOSTS:
                self.ALLOWED_HOSTS = ["*"]
        return self

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
