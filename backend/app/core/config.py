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

    # DSN for the test suite. Kept separate from DATABASE_URL so tests that
    # commit for real (background-task style) never touch dev data. Defaults
    # to DATABASE_URL with a "_test" suffix on the DB name.
    TEST_DATABASE_URL: str = (
        "postgresql+asyncpg://conciliador:conciliador@db:5432/autoconciliador_test"
    )

    # --- JWT auth (Phase 4) ---
    # Secret used to sign access tokens. MUST be overridden in .env with a
    # strong random value (e.g. `openssl rand -hex 32`). The default is only
    # a placeholder so the app boots in dev.
    SECRET_KEY: str = "change-me-in-env-generate-with-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Comma-separated origins allowed by CORS (frontend Vue in Phase 5).
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # --- StatementReviewer (tier 2, LLM second opinion — see llm_reviewer.py) ---
    # Off by default: NullStatementReviewer, zero cost, zero dependency. The
    # model (Qwen 2.5 7B Instruct) runs on a separate machine with a GPU, NOT
    # this host — this backend only ever speaks HTTP to an OpenAI-compatible
    # endpoint. If this project is deployed onto that same GPU machine,
    # LLM_BASE_URL is simply localhost/the docker-network service name there
    # — the code doesn't care which; only these 6 vars change per deploy.
    LLM_REVIEW_ENABLED: bool = False
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "qwen2.5:7b-instruct"
    LLM_API_KEY: str = ""
    LLM_TIMEOUT_SECONDS: float = 90.0
    LLM_MAX_LINEAS_CONTEXTO: int = 40


settings = Settings()
