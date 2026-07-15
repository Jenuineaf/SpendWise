from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "SpendWise"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Phase 4: LLM advisor
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None

    # Phase 4: email alerts
    EMAIL_BACKEND: str = "console"
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAIL_FROM: str = "noreply@spendwise.local"

    @field_validator("DATABASE_URL")
    @classmethod
    def _ensure_asyncpg_driver(cls, value: str) -> str:
        # Managed Postgres providers (Render, Railway, ...) hand out a plain
        # postgresql:// connection string; the app needs the asyncpg driver.
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
