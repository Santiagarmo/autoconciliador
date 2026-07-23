"""Application settings loaded from environment (.env)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Async SQLAlchemy DSN, e.g. postgresql+asyncpg://user:pass@host:5432/db
    DATABASE_URL: str = (
        "postgresql+asyncpg://conciliador:conciliador@localhost:5432/autoconciliador"
    )

    # Toggle SQL echo for debugging.
    DB_ECHO: bool = False


settings = Settings()
