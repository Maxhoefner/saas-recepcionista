from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables / .env.

    Values here are process-wide (infra/runtime config). Anything that varies
    per business (tenant) — assistant tone, working hours, WhatsApp number —
    lives in the database, not here.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_receptionist"

    JWT_SECRET: str = "change-me-in-.env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    LLM_PROVIDER: str = "anthropic"
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    AGENT_MAX_TOOL_ITERATIONS: int = 5

    # Dev-only default (like JWT_SECRET) — generate a real one for anything
    # beyond local dev: python -c "from cryptography.fernet import Fernet;
    # print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = "z3GfZNdioQ-bEiX0Mcej_MWYG4BQQTmkojRp2M3BWXI="

    WHATSAPP_PROVIDER: str = "meta"
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_API_BASE_URL: str = "https://graph.facebook.com/v21.0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
